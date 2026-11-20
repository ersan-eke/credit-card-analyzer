"""Replay a recorded extraction run offline through the real update_fees: per price list the calls, stop reasons,
content block types, output tokens and outcome. Never reaches the API: an unrecorded list is reported, not called.
Holdout banks print counts and the outcome class only, never rule text.

    uv run python evals/analyse_run.py evals/runs/extract-v8.json --fees out/v8-replay.json
"""

import argparse
import json
from pathlib import Path
from typing import NamedTuple

from cardcost import db
from cardcost.fees import CATALOG_DOCS, update_fees
from cardcost.llm import LLM, CacheMiss


class Row(NamedTuple):
    card: str
    calls: int
    stop_reasons: list[str]
    blocks: list[str]
    out_tokens: int
    outcome: str


class Tap:
    """Wraps an llm and keeps every response it returns."""

    def __init__(self, llm):
        self.llm, self.responses = llm, []

    def create(self, purpose, prompt_version, **kw):
        response = self.llm.create(purpose, prompt_version, **kw)
        self.responses.append(response)
        return response


def analyse(paths: list[Path], llm, conn, fees_out: Path) -> list[Row]:
    rows = []
    for path in paths:
        tap = Tap(llm)
        try:
            outcome = update_fees([path], fees_out, tap, conn)[path.stem]
        except CacheMiss:
            outcome = "not recorded"
        if outcome == "no fees found":  # extraction failed: the review queue holds why
            errors = [r["error"] for r in db.pending_reviews(conn) if r["card"] == path.stem and r["error"]]
            outcome = errors[-1][:200] if errors else outcome
        last = tap.responses[-1] if tap.responses else {}
        rows.append(
            Row(
                path.stem,
                len(tap.responses),
                [r.get("stop_reason") or "?" for r in tap.responses],
                [b["type"] for b in last.get("content") or []],
                sum((r.get("usage") or {}).get("output_tokens", 0) for r in tap.responses),
                outcome,
            )
        )
    return rows


def outcome_class(outcome: str) -> str:
    for needle, name in (
        ("extracted", "extracted"),
        ("not recorded", "not recorded"),
        ("max_tokens", "max_tokens"),
        ("did not call", "no tool call"),
        ("quote not found", "quote"),
        ("flagged", "flagged"),
    ):
        if needle in outcome:
            return name
    return "invalid"


def format_row(row: Row, holdout: bool) -> str:
    head = f"{row.card}: calls={row.calls} stop={','.join(row.stop_reasons)} out_tokens={row.out_tokens}"
    if holdout:
        return f"{head} {outcome_class(row.outcome)}"
    return f"{head} blocks={','.join(row.blocks)} {row.outcome}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run", help="the recording (cardcost ingest --record)")
    parser.add_argument("--fees", required=True, help="fresh output file for the replayed fees")
    parser.add_argument("--golden", default="evals/golden_real.json")
    args = parser.parse_args()
    if Path(args.fees).exists():
        parser.error(f"{args.fees} exists: an up-to-date fees file would skip the replay; use a fresh path")
    holdout = set(json.loads(Path(args.golden).read_text()).get("holdout", []))
    llm = LLM(cache_path=Path(args.run), live=False)  # the model must be the run's: it is part of the cache key
    for row in analyse(sorted(CATALOG_DOCS.glob("*.pdf")), llm, db.connect(":memory:"), Path(args.fees)):
        print(format_row(row, row.card.split("_")[0] in holdout))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
