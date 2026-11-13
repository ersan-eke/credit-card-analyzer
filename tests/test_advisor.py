from cardcost.advisor import Advisor
from cardcost.models import FeeSchedule

ROW = "Bargeldauszahlung am Geldautomaten | 3,0 % mind. 6,00 EUR | 1,0 % mind. 7,50 EUR"


def _fee(product, pct, mn, card="beta_card"):
    return FeeSchedule(
        card=card,
        product=product,
        percent=pct,
        min_eur=mn,
        source_file="beta_card.pdf",
        source_page=1,
        confidence=0.9,
        quote=ROW,
    )


BETA = {"beta_card": [_fee("Beta Classic", "3.0", "6.00"), _fee("Beta Gold", "1.0", "7.50")]}


def test_selected_product_and_default_expansion():
    assert list(Advisor(BETA, wallet=["beta_card:Gold"]).resolve("Bargeld")) == ["beta_card:Gold"]
    assert list(Advisor(BETA).resolve("Bargeld")) == ["beta_card:Beta Classic", "beta_card:Beta Gold"]


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
    fees = {"beta_card": [_fee("HVB Mastercard", "3.0", "6.00"), _fee("HVB Mastercard Gold", "1.0", "7.50")]}
    resolved = Advisor(fees, wallet=["beta_card:hvb mastercard"]).resolve("Bargeld")
    assert resolved["beta_card:hvb mastercard"].product == "HVB Mastercard"


def test_account_model_products_resolve_exactly():
    fees = {
        "beta_card": [_fee("HVB Mastercard", "3.0", "6.00"), _fee("HVB Mastercard / HVB AktivKonto", "1.0", "7.50")]
    }
    wallet = ["beta_card:HVB Mastercard", "beta_card:HVB Mastercard / HVB AktivKonto"]
    resolved = Advisor(fees, wallet=wallet).resolve("Bargeld")
    assert [f.product for f in resolved.values()] == ["HVB Mastercard", "HVB Mastercard / HVB AktivKonto"]


def test_extraction_prompt_asks_for_account_model_products():
    from cardcost.extract import SYSTEM

    assert "Kontomodell" in SYSTEM and "<card> / <Kontomodell>" in SYSTEM


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
    a = Advisor(BETA, wallet=["beta_card:Beta"])  # both products contain "Beta" and one extra word
    assert a.resolve("Bargeld") == {"beta_card:Beta": None}
    assert [f.product for f in a.choices["beta_card:Beta"]] == ["Beta Classic", "Beta Gold"]
    a.wallet = ["beta_card:Platin"]  # no match: every product of the card is a candidate
    a.resolve("Bargeld")
    assert [f.product for f in a.choices["beta_card:Platin"]] == ["Beta Classic", "Beta Gold"]
    assert a.choice_labels() == {"beta_card:Platin": ["beta_card:Beta Classic", "beta_card:Beta Gold"]}
    assert list(a.resolve("Bargeld", wallet=["beta_card:Gold"])) == ["beta_card:Gold"]  # one-off wallet
    assert a.choices == {}


def test_mentioned_cards_and_products():
    from cardcost.advisor import mentioned

    wallet = ["ing:VISA", "traderepublik", "hvb:HVB Mastercard", "hvb:HVB Mastercard AktivKonto", "beta_card:Gold"]
    assert mentioned("Was kostet Trade Republic?", wallet) == ["traderepublik"]  # one letter apart: fuzzy
    assert mentioned("Abhebung in Spanien", wallet) == []  # no false hit on short ids ("ing" in "Abhebung")
    assert mentioned("HVB Mastercard, 300 EUR", wallet) == ["hvb:HVB Mastercard"]
    assert mentioned("Mein HVB AktivKonto mit Mastercard", wallet) == ["hvb:HVB Mastercard AktivKonto"]
    assert mentioned("HVB oder ING?", wallet) == ["ing:VISA", "hvb:HVB Mastercard", "hvb:HVB Mastercard AktivKonto"]


def test_one_card_question_resolves_only_that_card():
    a = Advisor(
        BETA | {"alpha_card": [_fee(None, "3.0", "6.00", "alpha_card")]}, wallet=["alpha_card", "beta_card:Gold"]
    )
    assert list(a.resolve("Was kostet die Beta Gold für 300 EUR?")) == ["beta_card:Gold"]


def test_status_products_are_extracted_separately_and_priced_by_the_chosen_one():
    from decimal import Decimal

    from cardcost.calc import cost_line
    from cardcost.extract import SYSTEM
    from cardcost.models import Scenario

    assert "Aktivstatus" in SYSTEM and "<card> / mit Aktivstatus" in SYSTEM

    def dkb(status, fx, quote):
        return FeeSchedule(
            card="dkb",
            product=f"Visa Debitkarte / {status} Aktivstatus",
            percent="0",
            fx_percent=fx,
            source_file="dkb.pdf",
            source_page=1,
            confidence=0.9,
            quote=quote,
        )

    ohne = dkb("ohne", "2.2", "kostenlos seitens der DKB AG 2,20 % vom Umsatz")
    mit = dkb("mit", "0", "kostenlos seitens der DKB AG")
    advisor = Advisor({"dkb": [ohne, mit]}, wallet=["dkb"])
    advisor.resolve("Bargeld")
    assert list(advisor.choice_labels()) == []  # unqualified entry lists both products
    assert list(advisor.resolve("Bargeld")) == [
        "dkb:Visa Debitkarte / ohne Aktivstatus",
        "dkb:Visa Debitkarte / mit Aktivstatus",
    ]
    us = Scenario(kind="cash", amount_eur=Decimal(200), country="US")
    for status, want in (("ohne", "4.40"), ("mit", "0.00")):
        label = f"dkb:Visa Debitkarte / {status} Aktivstatus"
        fee = Advisor({"dkb": [ohne, mit]}, wallet=[label]).resolve("Bargeld")[label]
        assert cost_line(label, fee, us).total == Decimal(want)
