"""Score retrieval, extraction, cost (one-card questions), ranking (comparisons), facts (a stated fee or count) and
questions back (the advisor should ask instead of answering) for bm25 / vector / hybrid.

uv run python evals/run_eval.py            # replay recorded LLM answers (CI)
uv run python evals/run_eval.py --live     # call Claude on cache misses and record them
uv run python evals/run_eval.py --golden evals/golden_real.json   # draft set for the real price lists
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
from cardcost.numbers import find_numbers
from cardcost.retrieval import E5Embedder, Retriever

ROOT = Path(__file__).resolve().parent.parent
GATE = 0.9
EXPECTS = {
    "expected_cost": "cost",
    "expected_ranking": "ranking",
    "expected_fact": "fact",
    "expected_question": "question",
}


def _dec(v: str | None) -> Decimal | None:
    return None if v is None else Decimal(v)


def run_mode(mode: str, golden: dict, passages, embedder, llm) -> tuple[dict, list[str]]:
    advisor = Advisor(Retriever(passages, mode=mode, embedder=embedder), llm, wallet=golden["wallet"])
    hits = {k: [0, 0] for k in ["retrieval", "context", "extraction", *EXPECTS.values()]}
    failures = []
    for q in golden["questions"]:
        expect = next(v for k, v in EXPECTS.items() if k in q)
        advisor.wallet = q.get("wallet", golden["wallet"])
        if q["expected_page"] is not None:
            top = advisor.retriever.search(q["question"], card_id=q["card"], k=3)
            ok = any(p.page == q["expected_page"] for p in top)
            hits["retrieval"][0] += ok
            hits["retrieval"][1] += 1
            if not ok:
                failures.append(
                    f"[{mode}] {q['id']} retrieval: want p{q['expected_page']}, got {[p.page for p in top]}"
                )
            # what the extractor actually receives: question top-k plus the fixed fee-terms query
            ctx = advisor.passages_for(q["card"], q["question"])
            ok = any(p.page == q["expected_page"] for p in ctx)
            hits["context"][0] += ok
            hits["context"][1] += 1
            if not ok:
                failures.append(f"[{mode}] {q['id']} context: want p{q['expected_page']}, got {[p.page for p in ctx]}")
        scenario = Scenario(**q["scenario"])
        try:
            table = advisor.cost_table(q["question"], scenario)
        except Exception as e:  # noqa: BLE001 - an eval must report, not crash
            failures.append(f"[{mode}] {q['id']} pipeline error: {e!r}")
            hits["extraction"][1] += 1
            hits[expect][1] += 1
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
        if expect == "cost":  # one-card question: only that card's cost counts
            got_cost = next((ln.total for ln in table if ln.label == label), "missing")
            ok = got_cost == _dec(q["expected_cost"])
            hits["cost"][0] += ok
            hits["cost"][1] += 1
            if not ok:
                failures.append(f"[{mode}] {q['id']} cost {label}: want {q['expected_cost']}, got {got_cost}")
            continue
        if expect == "fact":
            fact = q["expected_fact"]
            got_fact = getattr(fee, fact["field"], None)
            ok = find_numbers(fact["answer"]) == [got_fact]
            hits["fact"][0] += ok
            hits["fact"][1] += 1
            if not ok:
                failures.append(
                    f"[{mode}] {q['id']} fact {label}.{fact['field']}: want {fact['answer']}, got {got_fact}"
                )
            continue
        if expect == "question":
            # shortcut: the advisor cannot ask back yet, so every expected question is a miss until #9 adds it
            hits["question"][1] += 1
            failures.append(f"[{mode}] {q['id']} question: want {q['expected_question']}, got an answer")
            continue
        ranking = [line.label for line in table]
        ok = ranking == q["expected_ranking"]
        hits["ranking"][0] += ok
        hits["ranking"][1] += 1
        if not ok:
            failures.append(f"[{mode}] {q['id']} ranking: want {q['expected_ranking']}, got {ranking}")
    return {k: v[0] / v[1] if v[1] else float("nan") for k, v in hits.items()}, failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all", choices=["all", "bm25", "vector", "hybrid"])
    ap.add_argument("--live", action="store_true", help="call the API on cache misses")
    ap.add_argument("--golden", type=Path, default=ROOT / "evals/golden.json")
    args = ap.parse_args()
    golden = json.loads(args.golden.read_text())
    passages = ingest_paths(sorted([*(ROOT / "samples").glob("*.pdf"), *(ROOT / "catalog/docs").glob("*.pdf")]))
    embedder = E5Embedder()
    llm = LLM(cache_path=ROOT / "evals/llm_cache.json", live=args.live)
    modes = ["bm25", "vector", "hybrid"] if args.mode == "all" else [args.mode]
    scores, failures = {}, []
    for mode in modes:
        scores[mode], f = run_mode(mode, golden, passages, embedder, llm)
        failures += f
    names = list(next(iter(scores.values())))
    print(f"\n{'mode':<8} " + " ".join(f"{'retrieval@3' if n == 'retrieval' else n:>11}" for n in names))
    for mode, s in scores.items():
        print(f"{mode:<8} " + " ".join(f"{s[n]:>11.2f}" for n in names))
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
