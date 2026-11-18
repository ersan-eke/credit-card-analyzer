"""Rule format, priced through the advisor (the seam the CLI and MCP use)."""

import json
from datetime import datetime
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


def cost(fees, amount="100", country="DE", kind="cash", used=None, days=0, **kw):
    s = Scenario(kind=kind, amount_eur=D(amount), country=country, used=used or {}, days=days, **kw)
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


def test_amount_thresholds_switch_the_price():
    fees = product(
        rule({"flat_eur": "1.95"}, quote="1,95 50", name="small", when={"amount": {"max": "50"}}),
        rule({"flat_eur": "1"}, quote="1 50 100", name="mid", when={"amount": {"min": "50", "max": "100"}}),
        rule({"flat_eur": "0"}, quote="kostenlos 100", name="big", when={"amount": {"min": "100"}}),
    )
    totals = [cost(fees, a).total for a in ("49.99", "50", "99.99", "100")]
    assert totals == [D("1.95"), D("1.00"), D("1.00"), D("0.00")]


def test_atm_network_picks_the_rule_and_operator_fee_follows_the_card_network():
    base = [
        rule({"flat_eur": "0"}, quote="kostenlos", name="own", when={"network": ["own"]}),
        rule({"flat_eur": "2"}, quote="2", name="group", when={"network": ["Cash Group"]}),
        rule({"flat_eur": "5"}, quote="5", name="other", when={"network": ["other"]}),
    ]
    fees = {
        "mc": [
            FeeSchedule(card="mc", network="Mastercard", source_file="c.pdf", source_page=1, confidence=1, rules=base)
        ],
        "visa": [
            FeeSchedule(card="visa", network="Visa", source_file="c.pdf", source_page=1, confidence=1, rules=base)
        ],
        "unk": [FeeSchedule(card="unk", source_file="c.pdf", source_page=1, confidence=1, rules=base)],
    }
    s = lambda **kw: {  # noqa: E731
        ln.label: ln for ln in Advisor(fees).cost_table("Bargeld", Scenario(kind="cash", amount_eur=D(100), **kw))
    }
    assert s(atm_network="own")["mc"].total == D("0.00")
    assert s(atm_network="Cash Group")["mc"].components == {"group": D("2.00")}
    assert s()["mc"].components == {"other": D("5.00")}  # unknown ATM: the dearest case
    fee = s(operator_fee={"Mastercard": D("3.50"), "Visa": D(0)})
    assert (fee["mc"].total, fee["visa"].total) == (D("8.50"), D("5.00"))
    assert fee["mc"].components["atm_operator_fee"] == D("3.50")
    assert (fee["unk"].total, fee["unk"].missing) == (None, ["atm_operator_fee"])  # card network unknown: not free


def test_stacked_rule_adds_to_the_base_rule():
    fees = product(
        rule({"percent": "1"}, quote="1", name="base"),
        rule({"percent": "2.2"}, quote="zzgl. 2,20", name="extra", stacks=True),
    )
    assert cost(fees, "100").components == {"base": D("1.00"), "extra": D("2.20")}


@pytest.mark.parametrize(
    ("at", "want"),
    [
        ("2026-11-20T22:00:00+00:00", "1.00"),  # Fri 17:00 New York (UTC-5) is Fri 22:00 UTC
        ("2026-11-20T21:59:00+00:00", "0.00"),
        ("2026-11-22T22:59:00+00:00", "1.00"),  # Sun 17:59 New York
        ("2026-11-22T23:00:00+00:00", "0.00"),  # Sun 18:00 New York
        ("2026-11-18T12:00:00+00:00", "0.00"),
    ],
)
def test_weekend_window_is_the_banks_own_in_its_time_zone(at, want):
    fees = product(rule({"percent": "1"}, quote="1", event=["payment"], when={"weekend": True}, stacks=True))
    assert cost(fees, kind="purchase", at=datetime.fromisoformat(at)).total == D(want)


def test_weekend_defaults_to_now():
    fees = product(rule({"percent": "1"}, quote="1", event=["payment"], when={"weekend": True}, stacks=True))
    assert cost(fees, kind="purchase").total in (D("0.00"), D("1.00"))


def test_held_currency_reduces_the_amount_exchanged():
    fees = product(
        rule(
            {"percent": "1"},
            quote="1 1000",
            name="fx",
            event=["payment"],
            when={"currency": FX},
            allowance={"amount_eur": "1000", "period": "calendar_month"},
        )
    )
    used = {"c": Usage(count=0, fx_eur=D(1000))}  # allowance used up
    assert cost(fees, "400", "US", "purchase", used).total == D("4.00")
    assert cost(fees, "400", "US", "purchase", used, held_eur=D(150)).total == D("2.50")
    assert cost(fees, "400", "US", "purchase", used, held_eur=D(900)).total == D("0.00")


def test_gambling_merchant_surcharge():
    fees = product(
        rule(
            {"percent": "3"},
            quote="3",
            name="gambling",
            event=["payment"],
            when={"merchant": ["gambling"]},
            stacks=True,
        )
    )
    assert cost(fees, kind="purchase").total == D("0.00")
    assert cost(fees, kind="purchase", merchant="gambling").components == {"gambling": D("3.00")}
