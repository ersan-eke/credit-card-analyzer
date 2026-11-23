"""Offline gates before a live extraction run: nothing here calls a model."""

import json
from pathlib import Path

import pytest

from cardcost.extract import CHARS_PER_TOKEN, MAX_INPUT_TOKENS, TOOL, _parse, build_prompt
from cardcost.ingest import read_text

ROOT = Path(__file__).parent.parent
GOLDEN = json.loads((ROOT / "evals/golden_real.json").read_text())
CARDS = sorted({label.partition(":")[0] for label in GOLDEN["rules"]})
RULE_PROPS = TOOL["input_schema"]["properties"]["products"]["items"]["properties"]["rules"]["items"]["properties"]


def _fill(value: dict | None, keys) -> dict | None:
    return None if value is None else {k: value.get(k) for k in keys}


def _tool_rule(rule: dict) -> dict:
    """A golden rule as the strict tool schema words it: every property present, lists empty for 'unset'."""
    when = rule.get("when") or {}
    out = {k: rule.get(k) for k in RULE_PROPS if k not in ("when", "price", "allowance")}
    out["name"] = rule.get("name") or rule["id"]
    out["stacks"] = bool(rule.get("stacks"))
    out["when"] = {
        k: (
            [{"name": n, "values": v} for n, v in (when.get(k) or {}).items()]
            if k == "facts"
            else bool(when.get(k))
            if k == "weekend"
            else _fill(when.get(k), ("min", "max"))
            if k == "amount"
            else when.get(k) or []
        )
        for k in RULE_PROPS["when"]["properties"]
    }
    out["price"] = _fill(rule["price"], RULE_PROPS["price"]["anyOf"][0]["properties"])
    out["allowance"] = _fill(rule.get("allowance"), RULE_PROPS["allowance"]["anyOf"][0]["properties"])
    return out


def golden_response(card: str) -> dict:
    products = [
        {"product": label.partition(":")[2] or None, "confidence": 1, "rules": [_tool_rule(r) for r in rules]}
        for label, rules in GOLDEN["rules"].items()
        if label.partition(":")[0] == card
    ]
    return {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "name": "record_fees", "input": {"products": products}}],
    }


def _union_parameters(node) -> int:
    if isinstance(node, dict):
        own = int("anyOf" in node or isinstance(node.get("type"), list))
        return own + sum(_union_parameters(v) for v in node.values())
    return sum(_union_parameters(v) for v in node) if isinstance(node, list) else 0


def check_strict(schema) -> None:
    """Every object closed and every property required, all the way down (Anthropic strict tool use)."""
    if isinstance(schema, dict):
        if "properties" in schema:
            assert schema["additionalProperties"] is False
            assert set(schema["required"]) == set(schema["properties"])
        for v in schema.values():
            check_strict(v)
    elif isinstance(schema, list):
        for v in schema:
            check_strict(v)


def test_schema_has_at_most_16_union_parameters():
    assert _union_parameters(TOOL["input_schema"]) <= 16  # Anthropic strict mode refuses more


@pytest.mark.parametrize("card", CARDS)
def test_golden_answer_passes_parse(card):
    pages = read_text(ROOT / f"catalog/docs/{card}.pdf")
    fees = _parse(card, f"{card}.pdf", golden_response(card), pages)
    assert sum(len(f.rules) for f in fees) == sum(
        len(rules) for label, rules in GOLDEN["rules"].items() if label.partition(":")[0] == card
    )


@pytest.mark.parametrize("card", CARDS)
def test_list_fits_the_token_budget(card):
    prompt = build_prompt(f"{card}.pdf", read_text(ROOT / f"catalog/docs/{card}.pdf"))
    assert len(prompt) // CHARS_PER_TOKEN <= MAX_INPUT_TOKENS


def test_weekend_false_is_no_window():
    # the strict schema has no null for a boolean, so every rule without a window arrives as weekend: false
    from cardcost.models import When

    assert When(weekend=False).weekend is None
    assert When(weekend=True).weekend is not None
