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
