from pathlib import Path

from cardcost.advisor import Advisor
from cardcost.ingest import ingest_paths
from cardcost.retrieval import Retriever

PASSAGES = ingest_paths(sorted((Path(__file__).parent.parent / "samples").glob("beta*.pdf")))
ROW = "Bargeldauszahlung am Geldautomaten | 3,0 % mind. 6,00 EUR | 1,0 % mind. 7,50 EUR"


def _item(product, pct, mn):
    return {
        "product": product,
        "percent": pct,
        "min_eur": mn,
        "currency": "EUR",
        "conditions": None,
        "fx_percent": None,
        "atm_operator_fee_eur": None,
        "cash_interest_pa": None,
        "source_file": "beta_card.pdf",
        "source_page": 1,
        "confidence": 0.9,
        "quote": ROW,
        "not_stated": [],
    }


class FakeLLM:
    def create(self, purpose, prompt_version, **kw):
        assert ROW in kw["messages"][0]["content"]  # the fee table reaches the extractor
        products = [_item("Beta Classic", "3.0", "6.00"), _item("Beta Gold", "1.0", "7.50")]
        return {"content": [{"type": "tool_use", "name": "record_fees", "input": {"products": products}}]}


def test_selected_product_and_default_expansion():
    r = Retriever(PASSAGES, mode="bm25")
    assert list(Advisor(r, FakeLLM(), wallet=["beta_card:Gold"]).resolve("Bargeld")) == ["beta_card:Gold"]
    assert list(Advisor(r, FakeLLM()).resolve("Bargeld")) == ["beta_card:Beta Classic", "beta_card:Beta Gold"]
    assert Advisor(r, FakeLLM(), wallet=["beta_card:Platin"]).resolve("Bargeld") == {"beta_card:Platin": None}


def test_parse_scenario():
    from decimal import Decimal

    from cardcost.advisor import parse_scenario

    s = parse_scenario("Welche Karte ist am günstigsten für 1.000 EUR Bargeld in den USA?")
    assert (s.kind, s.amount_eur, s.country) == ("cash", Decimal("1000"), "US")
    s = parse_scenario("Einkauf über 49,90 € in der Schweiz", days=3)
    assert (s.kind, s.amount_eur, s.country, s.days) == ("purchase", Decimal("49.90"), "CH", 3)
    assert parse_scenario("Geld abheben", amount_eur="200").amount_eur == Decimal("200")


def test_parse_usage():
    from decimal import Decimal

    import pytest

    from cardcost.advisor import parse_usage
    from cardcost.models import Usage

    assert parse_usage(["c24=2", "rev:Standard=3:150,50", "rev2=0::400"]) == {
        "c24": Usage(count=2),
        "rev:Standard": Usage(count=3, eur=Decimal("150.50")),
        "rev2": Usage(count=0, fx_eur=Decimal("400")),
    }
    with pytest.raises(ValueError):
        parse_usage(["c24"])


def test_exact_product_name_beats_substring():
    class TwoMastercards(FakeLLM):
        def create(self, purpose, prompt_version, **kw):
            products = [_item("HVB Mastercard", "3.0", "6.00"), _item("HVB Mastercard Gold", "1.0", "7.50")]
            return {"content": [{"type": "tool_use", "name": "record_fees", "input": {"products": products}}]}

    r = Retriever(PASSAGES, mode="bm25")
    fees = Advisor(r, TwoMastercards(), wallet=["beta_card:hvb mastercard"]).resolve("Bargeld")
    assert fees["beta_card:hvb mastercard"].product == "HVB Mastercard"


def test_account_model_products_resolve_exactly():
    class AccountModels(FakeLLM):
        def create(self, purpose, prompt_version, **kw):
            products = [_item("HVB Mastercard", "3.0", "6.00"), _item("HVB Mastercard / HVB AktivKonto", "1.0", "7.50")]
            return {"content": [{"type": "tool_use", "name": "record_fees", "input": {"products": products}}]}

    r = Retriever(PASSAGES, mode="bm25")
    wallet = ["beta_card:HVB Mastercard", "beta_card:HVB Mastercard / HVB AktivKonto"]
    fees = Advisor(r, AccountModels(), wallet=wallet).resolve("Bargeld")
    assert [f.product for f in fees.values()] == ["HVB Mastercard", "HVB Mastercard / HVB AktivKonto"]


def test_extraction_prompt_asks_for_account_model_products():
    from cardcost.extract import SYSTEM

    assert "Kontomodell" in SYSTEM and "<card> / <Kontomodell>" in SYSTEM
