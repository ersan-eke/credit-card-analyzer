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
