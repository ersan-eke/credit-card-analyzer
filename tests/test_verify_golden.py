import importlib.util
from decimal import Decimal
from pathlib import Path

_spec = importlib.util.spec_from_file_location("verify_golden", Path(__file__).parent.parent / "evals/verify_golden.py")
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)

LINES = ["Ersatzkarte 15,00 EUR", "An Geldautomaten", "in Euro kostenlos seitens der Bank", "Kontoführung kostenlos"]


def test_zero_fee_needs_a_fee_word_nearby():
    assert verify.lines_with("percent", Decimal(0), LINES) == ["An Geldautomaten ⏎ in Euro kostenlos seitens der Bank"]


def test_numbers_match_german_format_and_rank_field_lines_first():
    lines = ["Ersatzkarte 2,00 EUR", "Jede weitere Abhebung 2,00 EUR"]
    assert verify.lines_with("min_eur", Decimal("2.00"), lines)[0].endswith("Jede weitere Abhebung 2,00 EUR")
    assert verify.lines_with("min_eur", Decimal("3"), lines) == []
