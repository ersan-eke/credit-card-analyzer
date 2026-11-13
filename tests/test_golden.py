import json
from decimal import Decimal
from pathlib import Path

import pytest

from cardcost.numbers import find_numbers

EVALS = Path(__file__).parent.parent / "evals"
EXPECTATIONS = ("expected_cost", "expected_ranking", "expected_fact", "expected_question")


@pytest.mark.parametrize("name", ["golden.json", "golden_real.json"])
def test_each_question_has_exactly_one_expectation(name):
    # a one-card question must not fail because of another card's fee, so only a comparison is scored by ranking
    for q in json.loads((EVALS / name).read_text())["questions"]:
        assert sum(k in q for k in EXPECTATIONS) == 1, q["id"]
        compare = "günstigsten" in q["question"] or "Welche Karte" in q["question"]
        if "expected_ranking" in q:
            assert compare, q["id"]
        if compare:
            assert "expected_ranking" in q or "expected_question" in q, q["id"]


@pytest.mark.parametrize("name", ["golden.json", "golden_real.json"])
def test_fact_answer_states_the_expected_field_value(name):
    for q in json.loads((EVALS / name).read_text())["questions"]:
        if fact := q.get("expected_fact"):
            assert find_numbers(fact["answer"]) == [Decimal(q["expected_fields"][fact["field"]])], q["id"]


@pytest.mark.parametrize("name", ["golden.json", "golden_real.json"])
def test_question_back_names_a_kind(name):
    for q in json.loads((EVALS / name).read_text())["questions"]:
        if ask := q.get("expected_question"):
            assert ask["ask"] in ("usage", "product"), q["id"]
            assert ask["ask"] == "usage" or ask["card"] == q["card"], q["id"]


def test_review_corrections():
    qs = {q["id"]: q for q in json.loads((EVALS / "golden_real.json").read_text())["questions"]}
    assert qs["r04"]["expected_cost"] == "1.00"
    assert qs["r14"]["expected_fact"]["answer"] == "2,20 %"
    assert qs["r17"]["expected_fact"]["answer"] == "4"
    assert all(qs[i]["expected_question"]["ask"] == "usage" for i in ("r13", "r18", "r20"))
    assert all(qs[i]["expected_question"] == {"ask": "product", "card": "hvb"} for i in ("r09", "r10", "r15"))


@pytest.mark.parametrize("name", ["golden.json", "golden_real.json"])
def test_question_scope_matches_the_golden_card(name):
    from cardcost.advisor import COMPARE, mentioned

    golden = json.loads((EVALS / name).read_text())
    for q in golden["questions"]:
        if COMPARE.search(q["question"]):
            continue
        label = q["card"] + (f":{q['product']}" if q["product"] else "")
        assert mentioned(q["question"], q.get("wallet", golden["wallet"])) == [label], q["id"]
