"""Credit interest, holding fees and user-provided values, priced through the advisor."""

from decimal import Decimal as D

from cardcost.advisor import Advisor, parse_values
from cardcost.models import FeeSchedule, Price, Scenario


def rule(price: dict | None, quote: str, name: str, event: str, **kw) -> dict:
    return {"name": name, "event": [event], "price": price, "quote": quote, "page": 1} | kw


def card(*rules: dict) -> dict:
    return {"c": [FeeSchedule(card="c", source_file="c.pdf", source_page=1, confidence=1, rules=list(rules))]}


INTEREST = rule({"percent": "18.30"}, "Sollzins 18,30 %", "interest", "credit")
FREE_30 = INTEREST | {"interest_free_days": 30, "quote": "Sollzins 18,30 %, 30 Tage zinsfrei"}


def cost(fees, kind="purchase", amount="500", days=0, **kw):
    s = Scenario(kind=kind, amount_eur=D(amount), days=days, **kw)
    (line,) = Advisor(fees).cost_table("Frage", s)
    return line


def test_cash_accrues_from_day_one_even_when_paid_in_full():
    fees = card(rule({"flat_eur": "0"}, "kostenlos", "cash_fee", "atm"), FREE_30)
    line = cost(fees, kind="cash", amount="300", days=10, facts={"repayment_mode": "pays_in_full"})
    assert line.total == D("1.50")  # 300 x 18.30 % x 10 / 365


def test_paid_in_full_purchase_inside_the_interest_free_period_costs_nothing():
    fees = card(FREE_30)
    assert cost(fees, days=20, facts={"repayment_mode": "pays_in_full"}).total == D("0.00")
    # after the period the interest runs over all the days: 500 x 18.30 % x 40 / 365
    assert cost(fees, days=40, facts={"repayment_mode": "pays_in_full"}).total == D("10.03")


def test_paid_in_full_without_a_stated_period_is_free_by_the_due_date():
    assert cost(card(INTEREST), days=20, facts={"repayment_mode": "pays_in_full"}).total == D("0.00")


def test_instalments_accrue_over_every_day():
    line = cost(card(FREE_30), days=20, facts={"repayment_mode": "instalments"})
    assert line.total == D("5.01")  # 500 x 18.30 % x 20 / 365


def test_repayment_mode_is_asked_for_not_assumed():
    line = cost(card(FREE_30), days=20)
    assert line.total is None and line.missing == ["repayment_mode"]
    assert cost(card(FREE_30)).total == D("0.00")  # no days: nothing borrowed
    assert cost(card(rule({"flat_eur": "0"}, "kostenlos", "fee", "payment")), days=20).total == D("0.00")


def test_holding_fees_are_shown_not_ranked():
    fees = card(
        rule({"flat_eur": "4.90"}, "Kartenentgelt 4,90 € pro Monat", "card_fee", "holding", per="month"),
        rule(
            {"flat_eur": "29"},
            "Jahrespreis 29 €, entfällt bei 1000 € Umsatz",
            "annual_fee",
            "holding",
            per="year",
            waiver="bei 1000 € Umsatz im Jahr",
        ),
    )
    line = cost(fees)
    assert line.total == D("0.00")
    assert line.holding == [
        "card_fee 4.90 EUR pro Monat",
        "annual_fee 29 EUR pro Jahr (entfällt: bei 1000 € Umsatz im Jahr)",
    ]


def test_user_value_prices_an_unstated_rate_and_is_marked():
    fees = card(
        rule({"flat_eur": "0"}, "kostenlos", "cash_fee", "atm"),
        rule(None, "Sollzins siehe Preisaushang", "interest", "credit"),
    )
    unknown = cost(fees, kind="cash", amount="300", days=30)
    assert unknown.total is None and unknown.missing == ["interest"]
    given = {"c": {"interest": Price(percent=D("12"))}}
    line = cost(fees, kind="cash", amount="300", days=30, provided=given)
    assert line.total == D("2.96") and line.provided == ["interest"]  # 300 x 12 % x 30 / 365
    assert any("Nutzer" in n for n in line.notes)


def test_user_value_prices_an_unstated_fee_and_holding_fee():
    fees = card(
        rule(None, "in der App angezeigt", "cash_fee", "atm"),
        rule(None, "in der App angezeigt", "card_fee", "holding", per="month"),
    )
    given = {"c": {"cash_fee": Price(flat_eur=D("3")), "card_fee": Price(flat_eur=D("2"))}}
    line = cost(fees, kind="cash", amount="100", provided=given)
    assert line.total == D("3.00") and line.provided == ["cash_fee", "card_fee"]
    assert line.holding == ["card_fee 2 EUR pro Monat (Wert vom Nutzer)"]


def test_parse_values():
    assert parse_values(["c:Gold=cash_fee=3 EUR", "c=interest=12,5%"]) == {
        "c:Gold": {"cash_fee": Price(flat_eur=D("3"))},
        "c": {"interest": Price(percent=D("12.5"))},
    }


def test_the_answer_marks_the_users_value_and_shows_holding_fees():
    from cardcost.answer import template

    fees = card(
        rule(None, "in der App angezeigt", "cash_fee", "atm"),
        rule({"flat_eur": "4.90"}, "4,90 € pro Monat", "card_fee", "holding", per="month"),
    )
    s = Scenario(kind="cash", amount_eur=D(100), provided={"c": {"cash_fee": Price(flat_eur=D(3))}})
    text = template(Advisor(fees).cost_table("Frage", s), s)
    assert "Ihrem eigenen Wert" in text and "cash_fee" in text and "card_fee 4.90 EUR pro Monat" in text
