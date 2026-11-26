"""Offline gates before a live extraction run: nothing here calls a model."""


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


def test_weekend_false_is_no_window():
    # the strict schema has no null for a boolean, so every rule without a window arrives as weekend: false
    from cardcost.models import When

    assert When(weekend=False).weekend is None
    assert When(weekend=True).weekend is not None
