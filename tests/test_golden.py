import json
import tomllib
from decimal import Decimal
from pathlib import Path

import pytest

from cardcost.extract import _squash
from cardcost.ingest import read_text
from cardcost.models import Rule
from cardcost.numbers import find_numbers

ROOT = Path(__file__).parent.parent
EVALS = ROOT / "evals"
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


def _rules(golden: dict) -> dict[str, dict]:
    return {r["id"]: r for rules in golden["rules"].values() for r in rules}


@pytest.mark.parametrize("name", ["golden.json", "golden_real.json"])
def test_fact_answer_states_a_number_of_its_rule(name):
    golden = json.loads((EVALS / name).read_text())
    rules = _rules(golden)
    for q in golden["questions"]:
        if fact := q.get("expected_fact"):
            r = rules[fact["rule"]]
            stated = [
                *(r["price"] or {}).values(),
                *{k: v for k, v in (r["allowance"] or {}).items() if k != "period"}.values(),
            ]
            assert find_numbers(fact["answer"])[0] in {Decimal(str(v)) for v in stated if v is not None}, q["id"]


@pytest.mark.parametrize("name", ["golden.json", "golden_real.json"])
def test_question_back_names_a_kind(name):
    for q in json.loads((EVALS / name).read_text())["questions"]:
        if ask := q.get("expected_question"):
            assert ask["ask"] in ("usage", "product", "fact"), q["id"]
            assert ask["ask"] == "usage" or ask["card"] == q["card"], q["id"]


def test_review_corrections():
    qs = {q["id"]: q for q in json.loads((EVALS / "golden_real.json").read_text())["questions"]}
    assert qs["r04"]["expected_cost"] == "1.00"
    assert qs["r14"]["expected_fact"]["answer"] == "2,20 %"
    assert qs["r17"]["expected_fact"]["answer"] == "4"
    assert all(qs[i]["expected_question"]["ask"] == "usage" for i in ("r13", "r18", "r20"))
    assert all(qs[i]["expected_question"]["fact"] == "account_model" for i in ("r09", "r10"))


@pytest.mark.parametrize("name", ["golden.json", "golden_real.json"])
def test_question_scope_matches_the_golden_card(name):
    from cardcost.advisor import COMPARE, mentioned

    golden = json.loads((EVALS / name).read_text())
    for q in golden["questions"]:
        if COMPARE.search(q["question"]):
            continue
        label = q["card"] + (f":{q['product']}" if q["product"] else "")
        assert mentioned(q["question"], q.get("wallet", golden["wallet"])) == [label], q["id"]


def test_pending_questions_name_their_ticket():
    for name in ("golden.json", "golden_real.json"):
        for q in json.loads((EVALS / name).read_text())["questions"]:
            assert q.get("pending", "#").startswith("#"), q["id"]


def test_real_golden_has_rules_for_every_catalog_card():
    ids = {s["id"] for s in tomllib.loads((ROOT / "catalog/sources.toml").read_text())["source"]}
    rules = json.loads((EVALS / "golden_real.json").read_text())["rules"]
    assert {label.partition(":")[0] for label in rules} == ids


@pytest.mark.parametrize("name", ["golden.json", "golden_real.json"])
def test_expected_rules_are_valid_rules(name):
    for label, rules in json.loads((EVALS / name).read_text())["rules"].items():
        for r in rules:
            Rule.model_validate(
                {k: v for k, v in r.items() if k not in ("id", "review")}
            )  # numbers come from the quote
            assert r["id"], label


def _golden_rules():
    golden = json.loads((EVALS / "golden_real.json").read_text())
    return [(label, r) for label, rules in golden["rules"].items() for r in rules]


@pytest.mark.parametrize("label,rule", _golden_rules(), ids=lambda v: v if isinstance(v, str) else v["id"])
def test_golden_quotes_are_verbatim(label, rule):
    pages = read_text(ROOT / "catalog/docs" / f"{label.partition(':')[0]}.pdf")
    assert 1 <= rule["page"] <= len(pages)
    assert _squash(rule["quote"]) in _squash(pages[rule["page"] - 1])
