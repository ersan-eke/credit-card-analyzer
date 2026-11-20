"""The eval report: dev/holdout/example views, lists that returned nothing, label diff, history row."""

import importlib.util
import json
import sys
from pathlib import Path

EVALS = Path(__file__).parent.parent / "evals"
sys.path.insert(0, str(EVALS))  # run_eval imports rule_score as a sibling
_spec = importlib.util.spec_from_file_location("run_eval", EVALS / "run_eval.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)
import rule_score  # noqa: E402


def rule(price, id=None, **kw):
    return {
        "id": id,
        "event": ["atm"],
        "when": {},
        "price": {"flat_eur": price},
        "allowance": None,
        "stacks": False,
    } | kw


GOLDEN = {
    "holdout": ["ing"],
    "rules": {
        "dkb:Visa": [rule("1", "d1")],
        "ing": [rule("2", "i1")],
        "revolut_plus": [rule("3", "r1", used_as_example=True), rule("4", "r2")],
    },
}
GOT = {"dkb:Visa": [rule("1")], "revolut_plus": [rule("3"), rule("9")], "girocard": [rule("5")]}


def _score():
    return rule_score.score(GOLDEN["rules"], GOT, scored=set(GOLDEN["rules"]))


def test_views_split_holdout_dev_and_examples():
    v = ev.views(GOLDEN, _score())
    assert v["all"] == (2 / 4, 2 / 3)
    assert v["holdout"] == (0, 1)  # ing returned nothing
    assert v["dev"] == (2 / 3, 2 / 3)
    assert v["no_examples"] == (1 / 3, 1 / 2)  # r1 and the extracted rule that matched it are out
    assert v["no_example_banks"] == (1 / 2, 1)  # revolut out


def test_empty_lists_names_cards_with_no_label():
    assert ev.empty_lists(GOLDEN, GOT) == ["ing"]


def test_label_diff_reports_both_sides():
    extra, never = ev.label_diff(GOLDEN, GOT)
    assert extra == ["girocard"] and never == ["ing"]


def test_history_row_has_hashes_and_counts(tmp_path):
    golden = tmp_path / "g.json"
    golden.write_text(json.dumps(GOLDEN))
    row = ev.history_row("extract-v8", golden, ev.views(GOLDEN, _score()), ["ing"], (10, 5), 1, 2)
    assert row.startswith("| extract-v8 |") and row.endswith("|")
    assert ev.sha8(golden.read_bytes()) in row and "ing" in row and "10/5" in row


def test_a_product_with_no_rules_counts_as_returning_nothing():
    assert ev.empty_lists(GOLDEN, GOT | {"ing": []}) == ["ing"]
