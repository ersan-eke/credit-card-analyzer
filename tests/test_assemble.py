from decimal import Decimal

import pytest
from test_sections import C24_PAGE3

from cardcost.assemble import Condition, Document, build_rules, clean_product, merge_rules
from cardcost.sections import Layout, Section, layout, views

FEE = {
    "name": "Fee", "event": [], "cards": [], "only_for": [], "percent": "", "flat_eur": "", "min_eur": "",
    "max_eur": "", "free": False, "allowance_count": "", "allowance_amount": "", "allowance_period": "none",
    "amount_min": "", "amount_max": "", "interest_free_days": "", "per": "none", "waiver": "",
}  # fmt: skip


def _view(lines):
    s = Section("p1.0", 1, 0, lines, [], None)
    return views(s, Layout([], [], [s]))[0]


C24_VIEW = _view(["Mit der C24 Mastercard | 4 x 0,00 EUR 7", "Jede weitere | 2,00 EUR"])
FREE_VIEW = _view(["Bezahlen in EUR kostenfrei"])
PCT_VIEW = _view(["Fremdwährung | 1,75 %"])
ONE_CARD = Document(cards=["Card"], conditions=[], document_for=None, fee_headings=set(), table_columns={})
_lay = layout([C24_PAGE3])
_sec = next(s for s in _lay.sections if any("4 x 0,00 EUR" in x for x in s.lines))
C24_VIEWS = views(_sec, _lay)


def test_tags_become_numbers_and_quote_is_the_lines_they_sit_on():
    [(product, rule)] = build_rules(
        FEE | {"event": ["atm"], "allowance_count": "n1", "allowance_period": "calendar_month", "flat_eur": "n4"},
        C24_VIEW,
        ONE_CARD,
    )
    assert (product, rule.price.flat_eur, rule.allowance.count) == (None, Decimal("2.00"), 4)
    assert rule.quote == "\n".join(C24_VIEW.section.lines[0:2]) and rule.page == 1


def test_free_word_without_number_is_price_zero():
    [(_, r)] = build_rules(FEE | {"event": ["payment"], "free": True}, FREE_VIEW, ONE_CARD)
    assert r.price.flat_eur == 0


def test_no_price_and_not_free_is_unstated():
    [(_, r)] = build_rules(FEE | {"event": ["atm"]}, FREE_VIEW, ONE_CARD)
    assert r.price is None


def test_unknown_tag_and_fractional_count_raise():
    with pytest.raises(ValueError, match="n99"):
        build_rules(FEE | {"event": ["atm"], "flat_eur": "n99"}, C24_VIEW, ONE_CARD)
    with pytest.raises(ValueError, match="whole"):
        build_rules(FEE | {"event": ["atm"], "allowance_count": "n2", "allowance_period": "year"}, C24_VIEW, ONE_CARD)
    with pytest.raises(ValueError, match="period"):
        build_rules(FEE | {"event": ["atm"], "allowance_count": "n1", "flat_eur": "n4"}, C24_VIEW, ONE_CARD)


def test_only_for_becomes_facts_and_other_plans_of_a_one_plan_list_are_dropped():
    doc = ONE_CARD._replace(conditions=[Condition("Standard", "plan"), Condition("Plus", "plan")], document_for=0)
    assert build_rules(FEE | {"event": ["payment"], "percent": "n1", "only_for": [2]}, PCT_VIEW, doc) == []
    [(_, r)] = build_rules(FEE | {"event": ["payment"], "percent": "n1", "only_for": [1]}, PCT_VIEW, doc)
    assert r.when.facts is None
    hvb = ONE_CARD._replace(conditions=[Condition("HVB ExklusivKonto", "account_model")])
    [(_, r)] = build_rules(FEE | {"event": ["atm"], "flat_eur": "n1", "only_for": [1]}, PCT_VIEW, hvb)
    assert r.when.facts == {"account_model": ["HVB ExklusivKonto"]}


def test_condition_columns_become_facts():
    doc = ONE_CARD._replace(table_columns={0: "account_model"})
    view = next(v for v in C24_VIEWS if v.columns == ["C24 Pluskonto", "C24 Maxkonto"])
    [(_, r)] = build_rules(
        FEE | {"event": ["atm"], "allowance_count": "n1", "allowance_period": "calendar_month", "flat_eur": "n4"},
        view,
        doc,
    )
    assert r.when.facts == {"account_model": ["C24 Pluskonto", "C24 Maxkonto"]}


def test_cards_empty_means_every_card_and_one_card_lists_have_no_product():
    two = ONE_CARD._replace(cards=["Debitkarte", "Kreditkarte"])
    assert [p for p, _ in build_rules(FEE | {"event": ["atm"], "flat_eur": "n1"}, PCT_VIEW, two)] == [
        "Debitkarte",
        "Kreditkarte",
    ]
    assert [p for p, _ in build_rules(FEE | {"event": ["atm"], "flat_eur": "n1", "cards": [2]}, PCT_VIEW, two)] == [
        "Kreditkarte"
    ]


@pytest.mark.parametrize("raw,clean", [("Visa Debitkarte 1A", "Visa Debitkarte"), ("VISA Card [Debitkarte]", "VISA Card"),  # noqa: E501
                                       ("HVB Mastercard", "HVB Mastercard"), ("Visa Card Gold", "Visa Card Gold"),
                                       ("Card 2", "Card"), ("Visa (Kreditkarte)", "Visa")])  # fmt: skip
def test_clean_product(raw, clean):
    assert clean_product(raw) == clean


def test_merge_drops_repeats_of_the_same_fee():
    [(_, r)] = build_rules(FEE | {"event": ["atm"], "flat_eur": "n1"}, PCT_VIEW, ONE_CARD)
    assert merge_rules([(None, r), (None, r.model_copy(update={"name": "x"}))]) == {None: [r]}
