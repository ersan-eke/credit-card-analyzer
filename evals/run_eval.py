"""Score retrieval, extraction and ranking separately for bm25 / vector / hybrid.

uv run python evals/run_eval.py            # replay recorded LLM answers (CI)
uv run python evals/run_eval.py --live     # call Claude on cache misses and record them
Exit 1 if hybrid extraction accuracy < 0.9.
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from cardcost.advisor import Advisor
from cardcost.ingest import ingest_paths
from cardcost.llm import LLM
from cardcost.models import Scenario
from cardcost.retrieval import E5Embedder, Retriever

ROOT = Path(__file__).resolve().parent.parent
GATE = 0.9


def _dec(v: str | None) -> Decimal | None:
    return None if v is None else Decimal(v)


def run_mode(mode: str, golden: dict, passages, embedder, llm) -> tuple[dict, list[str]]:
    advisor = Advisor(Retriever(passages, mode=mode, embedder=embedder), llm, wallet=golden["wallet"])
    hits = {"retrieval": [0, 0], "extraction": [0, 0], "ranking": [0, 0]}
    failures = []
    for q in golden["questions"]:
        if q["expected_page"] is not None:
            top = advisor.retriever.search(q["question"], card_id=q["card"], k=3)
            ok = any(p.page == q["expected_page"] for p in top)
            hits["retrieval"][0] += ok
            hits["retrieval"][1] += 1
            if not ok:
                failures.append(
                    f"[{mode}] {q['id']} retrieval: want p{q['expected_page']}, got {[p.page for p in top]}"
                )
        scenario = Scenario(**q["scenario"])
        try:
            table = advisor.cost_table(q["question"], scenario)
        except Exception as e:  # noqa: BLE001 - an eval must report, not crash
            failures.append(f"[{mode}] {q['id']} pipeline error: {e!r}")
            hits["extraction"][1] += 1
            hits["ranking"][1] += 1
            continue
        label = q["card"] + (f":{q['product']}" if q["product"] else "")
        fee = advisor.fees.get(label)
        got = {f: getattr(fee, f, None) for f in q["expected_fields"]}
        want = {f: _dec(v) for f, v in q["expected_fields"].items()}
        ok = got == want
        hits["extraction"][0] += ok
        hits["extraction"][1] += 1
        if not ok:
            failures.append(f"[{mode}] {q['id']} extraction {label}: want {want}, got {got}")
        ranking = [line.label for line in table]
        ok = ranking == q["expected_ranking"]
        hits["ranking"][0] += ok
        hits["ranking"][1] += 1
        if not ok:
            failures.append(f"[{mode}] {q['id']} ranking: want {q['expected_ranking']}, got {ranking}")
    return {k: v[0] / v[1] for k, v in hits.items()}, failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all", choices=["all", "bm25", "vector", "hybrid"])
    ap.add_argument("--live", action="store_true", help="call the API on cache misses")
    args = ap.parse_args()
    golden = json.loads((ROOT / "evals/golden.json").read_text())
    passages = ingest_paths(sorted((ROOT / "samples").glob("*.pdf")))
    embedder = E5Embedder()
    llm = LLM(cache_path=ROOT / "evals/llm_cache.json", live=args.live)
    modes = ["bm25", "vector", "hybrid"] if args.mode == "all" else [args.mode]
    scores, failures = {}, []
    for mode in modes:
        scores[mode], f = run_mode(mode, golden, passages, embedder, llm)
        failures += f
    print(f"\n{'mode':<8} {'retrieval@3':>12} {'extraction':>11} {'ranking':>8}")
    for mode, s in scores.items():
        print(f"{mode:<8} {s['retrieval']:>12.2f} {s['extraction']:>11.2f} {s['ranking']:>8.2f}")
    print(f"\nLLM calls: {llm.calls} live, {llm.cache_hits} from cache")
    print(f"\n{len(failures)} failures:" if failures else "\nno failures")
    for f in failures:
        print("  " + f)
    gate_mode = "hybrid" if "hybrid" in scores else modes[0]
    if scores[gate_mode]["extraction"] < GATE:
        print(f"\nFAIL: {gate_mode} extraction {scores[gate_mode]['extraction']:.2f} < {GATE}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
