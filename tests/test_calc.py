from decimal import Decimal as D

import pytest

from cardcost.calc import cash_cost, cost_line, matrix, rank
from cardcost.models import FeeSchedule, Scenario, Usage


def fee(**kw) -> FeeSchedule:
    base = dict(card="c", source_file="c.pdf", source_page=1, confidence=1.0)
    nums = " ".join(str(v) for k, v in kw.items() if k != "product" and v is not None)
    return FeeSchedule(**(base | {"quote": nums or None} | kw))


ALPHA = fee(percent=D("2.0"), min_eur=D("5.00"), fx_percent=D("1.75"))
CLASSIC = fee(percent=D("3.0"), min_eur=D("6.00"), fx_percent=D("2.0"), cash_interest_pa=D("14.90"))
GOLD = fee(percent=D("1.0"), min_eur=D("7.50"), fx_percent=D("0.00"))
GAMMA = fee(fx_percent=D("1.5"), atm_operator_fee_eur=D("2.00"))


@pytest.mark.parametrize(("amount", "want"), [("100", "5.00"), ("250", "5.00"), ("300", "6.00"), ("0.10", "5.00")])
def test_cash_cost_minimum_crossover(amount, want):
    assert cash_cost(ALPHA, D(amount)) == D(want)


def test_cash_cost_rounds_half_up():
    assert cash_cost(fee(percent=D("1.5"), min_eur=None), D("0.33")) == D("0.00")  # 0.00495 -> 0.00
    assert cash_cost(fee(percent=D("2.5"), min_eur=None), D("10.10")) == D("0.25")  # 0.2525 -> 0.25
    assert cash_cost(fee(percent=D("2.5"), min_eur=None), D("10.30")) == D("0.26")  # 0.2575 -> 0.26
    assert cash_cost(fee(percent=D("1"), min_eur=None), D("0.50")) == D("0.01")  # 0.005 -> 0.01 (half-up)


def test_fx_only_outside_eurozone():
    assert cost_line("a", ALPHA, Scenario(kind="cash", amount_eur=D("300"), country="FR")).total == D("6.00")
    us = cost_line("a", ALPHA, Scenario(kind="cash", amount_eur=D("300"), country="US"))
    assert us.components == {"cash_fee": D("6.00"), "fx_fee": D("5.25")} and us.total == D("11.25")


def test_atm_operator_fee_only_abroad():
    f = fee(percent=D("1.0"), min_eur=D("2.00"), atm_operator_fee_eur=D("2.00"))
    assert cost_line("x", f, Scenario(kind="cash", amount_eur=D("100"), country="DE")).total == D("2.00")
    assert cost_line("x", f, Scenario(kind="cash", amount_eur=D("100"), country="AT")).total == D("4.00")


def test_interest_when_days_given():
    line = cost_line("c", CLASSIC, Scenario(kind="cash", amount_eur=D("300"), country="DE", days=30))
    assert line.components["interest"] == D("3.67") and line.total == D("12.67")


def test_missing_fee_never_becomes_zero():
    line = cost_line("g", GAMMA, Scenario(kind="cash", amount_eur=D("100")))
    assert line.total is None and line.missing == ["cash_fee"]
    no_rate = cost_line("a", ALPHA, Scenario(kind="cash", amount_eur=D("100"), days=10))
    assert no_rate.total is None and no_rate.missing == ["cash_interest"]
    assert cost_line("z", None, Scenario(kind="cash", amount_eur=D("100"))).missing == ["fee document"]


def test_purchase_uses_only_fx():
    s = Scenario(kind="purchase", amount_eur=D("200"), country="US")
    assert [
        (ln.label, ln.total) for ln in rank({"alpha": ALPHA, "classic": CLASSIC, "gold": GOLD, "gamma": GAMMA}, s)
    ] == [("gold", D("0.00")), ("gamma", D("3.00")), ("alpha", D("3.50")), ("classic", D("4.00"))]


def test_rank_unknown_last_and_ties_by_label():
    s = Scenario(kind="cash", amount_eur=D("250"))
    order = [ln.label for ln in rank({"gamma": GAMMA, "gold": GOLD, "classic": CLASSIC, "alpha": ALPHA}, s)]
    assert order == ["alpha", "classic", "gold", "gamma"]  # classic = gold = 7.50, tie by label


def test_matrix_bands_and_crossover():
    bands = matrix({"alpha": ALPHA, "gold": GOLD}, kind="cash", country="DE", max_amount=1000)
    assert bands == [(1, 375, "alpha"), (376, 1000, "gold")]  # 2% of 375 = 7.50 = gold min; tie -> label


C24 = fee(min_eur=D("2.00"), free_count=D("4"))  # "4 x 0,00 EUR", then 2,00 EUR per withdrawal
REVOLUT = fee(percent=D("2"), min_eur=D("1"), free_count=D("5"), free_amount_eur=D("200"))
TRADE = fee(min_eur=D("1"), free_from_eur=D("100"))  # "1 € für Abhebungen unter 100 €"


def _cash(amount, **used) -> Scenario:
    return Scenario(kind="cash", amount_eur=D(amount), used={k: Usage(**v) for k, v in used.items()})


def test_free_count_allowance():
    assert cost_line("c24", C24, _cash("300", c24={"count": 3})).total == D("0.00")
    assert cost_line("c24", C24, _cash("300", c24={"count": 4})).total == D("2.00")


def test_unknown_usage_assumes_allowance_used_up():
    line = cost_line("c24", C24, _cash("300"))
    assert line.total == D("2.00") and "angenommen" in line.notes[0]
    # Revolut also caps the free amount: a count alone is not enough to call it free
    assert cost_line("rev", REVOLUT, _cash("50", rev={"count": 0})).total == D("1.00")


def test_free_amount_cap_whichever_first():
    assert cost_line("rev", REVOLUT, _cash("50", rev={"count": 1, "eur": "150"})).total == D("0.00")
    assert cost_line("rev", REVOLUT, _cash("10", rev={"count": 5, "eur": "0"})).total == D("1.00")


def test_partly_free_withdrawal_charges_only_the_part_above_the_allowance():
    # "Bis zu ... 200 € ... gebührenfrei. Weitere Abhebungen werden mit 2 % ... oder 1 € berechnet"
    assert cost_line("rev", REVOLUT, _cash("100", rev={"count": 2, "eur": "150"})).total == D("1.00")  # 2 % of 50
    assert cost_line("rev", REVOLUT, _cash("150", rev={"count": 2, "eur": "150"})).total == D("2.00")  # 2 % of 100
    assert cost_line("rev", REVOLUT, _cash("150", rev={"count": 2, "eur": "250"})).total == D("3.00")  # none left


def test_free_from_amount():
    assert cost_line("tr", TRADE, _cash("99.99")).total == D("1.00")
    assert cost_line("tr", TRADE, _cash("100")).total == D("0.00")


def test_usage_matches_card_or_product_label():
    s = _cash("300", c24={"count": 0})
    assert s.usage_for("c24:Smartkonto") == Usage(count=0)
    assert cost_line("c24:Smartkonto", C24, s).total == D("0.00")


REV_FX = fee(
    percent=D("2"), min_eur=D("1"), fx_percent=D("0.5"), fx_free_eur=D("1000")
)  # Wechsellimit 1.000 EUR, 0,5 %


def _buy(amount, **used) -> Scenario:
    return Scenario(kind="purchase", amount_eur=D(amount), country="US", used={k: Usage(**v) for k, v in used.items()})


def test_fx_allowance_charges_only_the_excess():
    assert cost_line("rev", REV_FX, _buy("200", rev={"count": 0, "fx_eur": "500"})).total == D("0.00")
    assert cost_line("rev", REV_FX, _buy("300", rev={"count": 0, "fx_eur": "900"})).total == D("1.00")  # 0.5 % of 200


def test_fx_allowance_unknown_usage_charges_full_amount():
    line = cost_line("rev", REV_FX, _buy("300"))
    assert line.total == D("1.50") and "angenommen" in line.notes[0]


def test_cards_without_fx_allowance_unchanged():
    assert cost_line("a", ALPHA, _buy("200", a={"count": 0, "fx_eur": "0"})).total == D("3.50")


def test_matrix_uses_allowance_usage():
    fees = {"c24": C24, "rev": REVOLUT}
    assert matrix(fees, "cash", "DE", 300) == [(1, 99, "rev"), (100, 300, "c24")]  # both allowances assumed used up
    assert matrix(fees, "cash", "DE", 300, used={"c24": Usage(count=0)}) == [(1, 300, "c24")]
