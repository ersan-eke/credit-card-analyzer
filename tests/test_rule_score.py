"""Golden eval seam: expected rules + extracted rules -> recall and precision, `when` compared by meaning."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("rule_score", Path(__file__).parent.parent / "evals/rule_score.py")
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)


def rule(price, event=("atm",), **kw):
    return {"event": list(event), "when": {}, "price": price, "allowance": None, "stacks": False, **kw}


def score(expected, extracted, countries=()):
    return rs.score({"c": expected}, {"c": extracted}, countries)


def test_identical_rules_score_one():
    r = rule({"percent": "2", "min_eur": "5"})
    s = score([r], [r])
    assert (s.recall, s.precision) == (1, 1)


def test_numbers_compare_as_values_not_spelling():
    s = score([rule({"percent": "2.0"})], [rule({"percent": "2"})])
    assert (s.recall, s.precision) == (1, 1)


def test_wrong_value_costs_both_sides_and_extra_rule_costs_precision():
    s = score([rule({"flat_eur": "2"})], [rule({"flat_eur": "3"})])
    assert (s.recall, s.precision) == (0, 0)
    s = score([rule({"flat_eur": "2"})], [rule({"flat_eur": "2"}), rule({"flat_eur": "9"}, event=["payment"])])
    assert (s.recall, s.precision) == (1, 0.5)


def test_allowance_and_stacking_are_part_of_the_rule():
    a = {"count": 4, "period": "calendar_month"}
    assert score([rule({"flat_eur": "2"}, allowance=a)], [rule({"flat_eur": "2"})]).recall == 0
    assert score([rule({"flat_eur": "2"}, stacks=True)], [rule({"flat_eur": "2"})]).recall == 0


def test_event_list_is_split_per_event():
    s = score([rule({"percent": "2"}, event=["atm", "payment"])], [rule({"percent": "2"})])
    assert (s.recall, s.precision) == (0.5, 1)


def test_unstated_price_matches_unstated_price():
    assert score([rule(None, event=["credit"])], [rule(None, event=["credit"])]).recall == 1


def test_when_matches_by_cases_not_spelling():
    eur_eea = {"currency": ["EUR"], "region": ["EEA"]}
    by_country = {"country": ["FR", "IT", "ES"]}
    # equal over DE/FR/PL/US only if the grid has no IT or ES: the golden scenarios supply them
    same = score([rule({"flat_eur": "5"}, when=eur_eea)], [rule({"flat_eur": "5"}, when=by_country)], ["FR", "IT"])
    assert same.recall == 0  # a country list misses the other euro countries (grid adds DE, FR, PL, US + FR, IT)
    full = {"country": ["AT", "BE", "FR", "IT", "ES", "NL", "PT"]}
    same = score([rule({"flat_eur": "5"}, when=eur_eea)], [rule({"flat_eur": "5"}, when=full)], ["FR", "IT"])
    assert same.recall == 1


def test_amount_boundary_is_inclusive_min_exclusive_max():
    under_100 = {"amount": {"max": "100"}}
    assert score([rule({"flat_eur": "1"}, when=under_100)], [rule({"flat_eur": "1"}, when=under_100)]).recall == 1
    off_by_one = {"amount": {"max": "101"}}
    assert score([rule({"flat_eur": "1"}, when=under_100)], [rule({"flat_eur": "1"}, when=off_by_one)]).recall == 0
    from_150 = {"amount": {"min": "150"}}
    assert (
        score(
            [rule({"flat_eur": "0"}, when=from_150)], [rule({"flat_eur": "0"}, when={"amount": {"min": "151"}})]
        ).recall
        == 0
    )


def test_network_weekend_and_fact_conditions():
    for key, a, b in [
        ("network", ["own"], ["other"]),
        ("weekend", True, False),
        ("facts", {"account_model": ["AktivKonto"]}, {"account_model": ["PlusKonto"]}),
    ]:
        assert score([rule({"flat_eur": "1"}, when={key: a})], [rule({"flat_eur": "1"}, when={key: a})]).recall == 1
        assert score([rule({"flat_eur": "1"}, when={key: a})], [rule({"flat_eur": "1"}, when={key: b})]).recall == 0


def test_found_gives_the_extracted_rule_for_an_expected_id():
    exp = rule({"percent": "2.2"}, id="x")
    got = rule({"percent": "2.20"}, name="whatever")
    s = score([exp], [got])
    assert s.found["x"] is got


def test_extracted_products_outside_the_golden_hurt_precision():
    s = rs.score({"c": [rule({"flat_eur": "1"})]}, {"c": [rule({"flat_eur": "1"})], "d": [rule({"flat_eur": "1"})]}, ())
    assert (s.recall, s.precision) == (1, 0.5)
