"""Offline routed estimate for a catalog price list."""

import importlib.util
from pathlib import Path

from cardcost.ingest import read_text

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("section_stats", ROOT / "evals/section_stats.py")
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)


def test_stats_count_routes_and_tokens():
    s = ss.stats("tfbank_mastercard_gold", read_text(ROOT / "catalog/docs/tfbank_mastercard_gold.pdf"))
    assert s["views"] >= 3 and s["route_calls"] >= s["routed"] and s["triage"] <= s["views"]
    for count, tokens in (
        ("route_calls", "route_tokens"),
        ("triage", "triage_tokens"),
        ("triage", "triage_route_tokens"),
    ):
        assert (s[tokens] > 0) == (s[count] > 0)
    assert s["doc_tokens"] > 0
