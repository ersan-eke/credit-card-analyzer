import json
from pathlib import Path

import pytest

EVALS = Path(__file__).parent.parent / "evals"


@pytest.mark.parametrize("name", ["golden.json", "golden_real.json"])
def test_single_card_questions_check_cost_comparisons_check_ranking(name):
    # a one-card question must not fail because of another card's fee, so it is scored by its cost alone
    for q in json.loads((EVALS / name).read_text())["questions"]:
        assert ("expected_cost" in q) != ("expected_ranking" in q), q["id"]
        compare = "günstigsten" in q["question"] or "Welche Karte" in q["question"]
        assert compare == ("expected_ranking" in q), q["id"]


@pytest.mark.parametrize("name", ["golden.json", "golden_real.json"])
def test_question_scope_matches_the_golden_card(name):
    from cardcost.advisor import COMPARE, mentioned

    golden = json.loads((EVALS / name).read_text())
    for q in golden["questions"]:
        if "expected_ranking" in q:
            assert COMPARE.search(q["question"]), q["id"]
            continue
        label = q["card"] + (f":{q['product']}" if q["product"] else "")
        assert mentioned(q["question"], q.get("wallet", golden["wallet"])) == [label], q["id"]
