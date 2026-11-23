"""Offline section and token estimate for a catalog price list."""

import importlib.util
from pathlib import Path

from cardcost.ingest import read_text

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("section_stats", ROOT / "evals/section_stats.py")
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)


def test_stats_count_views_and_tokens():
    s = ss.stats("tfbank_mastercard_gold", read_text(ROOT / "catalog/docs/tfbank_mastercard_gold.pdf"))
    assert s["views"] >= 3 and s["section_tokens"] > s["views"] * 300
