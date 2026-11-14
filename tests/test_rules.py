"""Rule format, priced through the advisor (the seam the CLI and MCP use)."""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest

from cardcost.advisor import Advisor
from cardcost.fees import read_fees
from cardcost.models import FeeSchedule, Scenario, Usage

ROOT = Path(__file__).parent.parent
FX = ["EEA_non_EUR", "other"]


def product(*rules: dict, name: str = "P") -> dict:
    return {
        "c": [FeeSchedule(card="c", product=name, source_file="c.pdf", source_page=1, confidence=1, rules=list(rules))]
    }


def rule(price: dict | None, quote: str = "1", name: str = "fee", **kw) -> dict:
    return {"name": name, "event": ["atm"], "price": price, "quote": quote, "page": 1} | kw


def cost(fees, amount="100", country="DE", kind="cash", used=None, days=0):
    s = Scenario(kind=kind, amount_eur=D(amount), country=country, used=used or {}, days=days)
    (line,) = Advisor(fees).cost_table("Bargeld", s)
    return line


def test_sample_questions_are_answered_from_rules():
    fees = read_fees([ROOT / "samples/fees.json"])
    assert all(f.rules for fs in fees.values() for f in fs)
    golden = json.loads((ROOT / "evals/golden.json").read_text())
    advisor = Advisor(fees, wallet=golden["wallet"])
    for q in golden["questions"]:
        if "expected_cost" not in q:
            continue
        label = q["card"] + (f":{q['product']}" if q["product"] else "")
        (line,) = advisor.cost_table(q["question"], Scenario(**q["scenario"]), wallet=[label])
        want = q["expected_cost"]
        assert (None if line.total is None else str(line.total)) == want, q["id"]
    s = Scenario(kind="cash", amount_eur=D(300), country="DE")
    assert [ln.label for ln in advisor.cost_table("Welche Karte", s)] == [
        "alpha_card",
        "beta_card:Gold",
        "beta_card:Classic",
        "gamma_card",
    ]


@pytest.mark.parametrize(
    ("price", "amount", "want"),
    [
        ({"percent": "2", "min_eur": "5"}, "100", "5.00"),
        ({"percent": "2", "min_eur": "5"}, "300", "6.00"),
        ({"percent": "2", "max_eur": "5"}, "1000", "5.00"),
        ({"flat_eur": "1.50", "percent": "1"}, "100", "2.50"),
        ({"flat_eur": "0"}, "100", "0.00"),
    ],
)
def test_percent_flat_minimum_maximum(price, amount, want):
    assert cost(product(rule(price, quote="2 5 1 1,50 0")), amount).total == D(want)


def test_most_specific_rule_wins_and_a_tie_is_an_error():
    broad = rule({"flat_eur": "5"}, quote="5", name="broad")
    fr = rule({"flat_eur": "1"}, quote="1", name="fr", when={"country": ["FR"]})
    assert cost(product(broad, fr), country="FR").total == D("1.00")
    assert cost(product(broad, fr), country="IT").total == D("5.00")
    abroad = rule({"flat_eur": "2"}, quote="2", name="abroad", when={"region": ["EEA"]})
    with pytest.raises(ValueError, match="tie"):
        cost(product(fr, abroad), country="FR")


def test_currency_and_region_conditions():
    fees = product(
        rule({"flat_eur": "1"}, name="base"),
        rule({"percent": "2"}, quote="2", name="fx", when={"currency": FX}, stacks=True),
        rule({"flat_eur": "3"}, quote="3", name="abroad", when={"region": ["EEA", "outside_EEA"]}, stacks=True),
    )
    assert cost(fees, "100", "DE").components == {"base": D("1.00")}
    assert cost(fees, "100", "FR").components == {"base": D("1.00"), "abroad": D("3.00")}  # euro abroad: no FX
    assert cost(fees, "100", "PL").components == {"base": D("1.00"), "fx": D("2.00"), "abroad": D("3.00")}
    assert cost(fees, "100", "US").total == D("6.00")


def test_foreign_currency_needs_a_stated_fx_price():
    ln = cost(product(rule({"flat_eur": "1"})), country="US")
    assert (ln.total, ln.missing) == (None, ["fx_fee"])


@pytest.mark.parametrize(
    ("used", "want"),
    [
        (None, "2.00"),  # unknown usage counts as used up
        (Usage(count=1, eur=D(0)), "0.00"),
        (Usage(count=2, eur=D(0)), "2.00"),  # count reached first
        (Usage(count=0, eur=D(200)), "2.00"),  # amount reached first
        (Usage(count=0, eur=D(150)), "1.00"),  # only the part above the free amount is charged
    ],
)
def test_allowance_by_count_or_amount_whichever_first(used, want):
    allowance = {"count": 2, "amount_eur": "200", "period": "rolling_month"}
    fees = product(rule({"percent": "2"}, quote="2 200", allowance=allowance))
    assert cost(fees, "100", used={"c": used} if used else {}).total == D(want)


def test_count_only_allowance_does_not_need_an_amount():
    fees = product(rule({"flat_eur": "3"}, quote="3 4", allowance={"count": 4, "period": "calendar_month"}))
    assert cost(fees, used={"c": Usage(count=3)}).total == D("0.00")
    assert cost(fees, used={"c": Usage(count=4)}).total == D("3.00")


def test_fx_allowance_counts_exchanged_amount():
    fees = product(
        rule(
            {"percent": "0.5"},
            quote="0,5 1000",
            name="fx",
            event=["payment"],
            when={"currency": FX},
            allowance={"amount_eur": "1000", "period": "calendar_month"},
        )
    )
    s = lambda fx: cost(fees, "400", "US", "purchase", {"c": Usage(count=0, fx_eur=D(fx))}).total  # noqa: E731
    assert (s("0"), s("800"), s("1000")) == (D("0.00"), D("1.00"), D("2.00"))


def test_unstated_price_is_unknown_never_free():
    known = FeeSchedule(
        card="k", source_file="k.pdf", source_page=1, confidence=1, rules=[rule({"flat_eur": "9"}, quote="9")]
    )
    fees = product(rule(None, quote="siehe Preisverzeichnis", name="cash_fee")) | {"k": [known]}
    table = Advisor(fees).cost_table("Bargeld", Scenario(kind="cash", amount_eur=D(100)))
    assert [(ln.label, ln.total) for ln in table] == [("k", D("9.00")), ("c", None)]
    assert table[-1].missing == ["cash_fee"]


def test_no_cash_rule_is_unknown_and_interest_needs_a_credit_rule():
    assert cost(product(rule({"flat_eur": "1"}, event=["payment"]))).missing == ["cash_fee"]
    atm_only = product(rule({"flat_eur": "1"}))
    assert cost(atm_only, days=30).missing == ["cash_interest"]
    credit = rule({"percent": "14.90"}, quote="14,90", name="interest", event=["credit"])
    assert cost(product(rule({"flat_eur": "1"}), credit), "300", days=30).total == D("1.00") + D("3.67")


def test_rule_numbers_must_come_from_its_quote():
    with pytest.raises(ValueError, match="does not appear in quote"):
        FeeSchedule(
            card="c", source_file="c.pdf", source_page=1, confidence=1, rules=[rule({"percent": "3"}, quote="2 %")]
        )
    assert cost(product(rule({"flat_eur": "0"}, quote="kostenlos"))).total == D("0.00")
