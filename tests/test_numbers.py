from decimal import Decimal

import pytest

from cardcost.numbers import find_numbers, number_spans, parse_german_decimal, to_cents


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.234,56", "1234.56"),
        ("2,5 %", "2.5"),
        ("5,00 EUR", "5.00"),
        ("1.000", "1000"),
        ("0,5", "0.5"),
        ("14,90 % p.a.", "14.90"),
        ("1.234.567,8", "1234567.8"),
        ("300", "300"),
    ],
)
def test_parse_german_decimal(text, expected):
    assert parse_german_decimal(text) == Decimal(expected)


@pytest.mark.parametrize("bad", ["", "abc", "1,2,3", "1.23.4"])
def test_parse_german_decimal_rejects(bad):
    with pytest.raises(ValueError):
        parse_german_decimal(bad)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.005", "0.01"), ("2.675", "2.68"), ("2.674", "2.67"), ("6", "6.00")],
)
def test_to_cents_half_up(value, expected):
    assert to_cents(Decimal(value)) == Decimal(expected)


def test_find_numbers_german_and_english():
    found = find_numbers("Kosten 6,00 EUR bzw. 1.234,56 EUR, also 2.5 % und 300 EUR")
    assert found == [Decimal("6.00"), Decimal("1234.56"), Decimal("2.5"), Decimal("300")]


def test_number_spans_match_find_numbers_and_give_positions():
    text = "4 x 0,00 EUR 7 | 1.234,56 EUR | 2%"
    spans = number_spans(text)
    assert [v for _, _, v in spans] == find_numbers(text)
    assert [text[s:e] for s, e, _ in spans] == ["4", "0,00", "7", "1.234,56", "2"]
