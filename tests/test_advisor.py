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


def test_k_grows_with_document_size():
    from cardcost.models import Passage

    big = [
        Passage(id=f"big:p{i}:0", card_id="big", file="big.pdf", page=i, text=f"Bargeld Seite {i}")
        for i in range(1, 13)
    ]
    a = Advisor(Retriever(big + PASSAGES, mode="bm25"), FakeLLM())
    assert (a.k_for("big"), a.k_for("beta_card")) == (4, 3)
    assert len(a.retriever.search("Bargeld", "big", a.k_for("big"))) == 4


def test_fee_query_reaches_revolut_fx_section():
    # Revolut calls its FX fee "Wechselgebühr" / "Wechsellimit" (p5); the fee-terms query must find it for any question
    rev = ingest_paths([Path(__file__).parent.parent / "samples/preis-leistung-revolut.pdf"])
    a = Advisor(Retriever(rev, mode="bm25"), FakeLLM())
    assert 5 in {p.page for p in a.passages_for("preis-leistung-revolut", "Was kostet das?")}


def test_match_product_by_words():
    from cardcost.advisor import match_product
    from cardcost.models import FeeSchedule

    def f(name):
        return FeeSchedule(card="hvb", product=name, source_file="x.pdf", source_page=1, confidence=1.0)

    def names(found):
        return [x.product for x in found]

    options = [f("HVB Mastercard"), f("HVB Mastercard Gold"), f("HVB Mastercard (HVB AktivKonto)")]
    assert names(match_product("hvb mastercard", options)) == ["HVB Mastercard"]  # exact beats fewer words
    assert names(match_product("HVB Mastercard / HVB AktivKonto", options)) == ["HVB Mastercard (HVB AktivKonto)"]
    assert names(match_product("AktivKonto", options)) == ["HVB Mastercard (HVB AktivKonto)"]
    assert names(match_product("Gold", options)) == ["HVB Mastercard Gold"]
    assert match_product("Platinum", options) == []
    tie = [f("HVB Mastercard Gold"), f("HVB Mastercard Basis")]
    assert names(match_product("Mastercard", tie)) == ["HVB Mastercard Gold", "HVB Mastercard Basis"]  # user picks


def test_unresolved_product_offers_the_candidates():
    r = Retriever(PASSAGES, mode="bm25")
    a = Advisor(r, FakeLLM(), wallet=["beta_card:Beta"])  # both products contain "Beta" and one extra word
    assert a.resolve("Bargeld") == {"beta_card:Beta": None}
    assert [f.product for f in a.choices["beta_card:Beta"]] == ["Beta Classic", "Beta Gold"]
    a.wallet = ["beta_card:Platin"]  # no match: every product of the card is a candidate
    a.resolve("Bargeld")
    assert [f.product for f in a.choices["beta_card:Platin"]] == ["Beta Classic", "Beta Gold"]
    assert a.choice_labels() == {"beta_card:Platin": ["beta_card:Beta Classic", "beta_card:Beta Gold"]}
    assert list(a.resolve("Bargeld", wallet=["beta_card:Gold"])) == ["beta_card:Gold"]  # one-off wallet
    assert a.choices == {}
