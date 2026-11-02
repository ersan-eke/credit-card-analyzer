from decimal import Decimal as D

import pytest

from cardcost.calc import cash_cost, cost_line, matrix, rank
from cardcost.models import FeeSchedule, Scenario


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
