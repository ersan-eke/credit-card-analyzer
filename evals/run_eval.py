"""Score extraction (recall and precision of rules), cost (one-card questions), ranking (comparisons), facts (a stated
fee or count) and questions back (the advisor should ask instead of answering). All of it is read from the committed
fees files (samples/fees.json, catalog/fees.json), so it needs no LLM and no embedding model.

uv run python evals/run_eval.py
uv run python evals/run_eval.py --golden evals/golden_real.json   # the real price lists
Exit 1 if rule recall or precision < 0.9. Questions marked `pending` name the ticket whose calculator they wait for and
are listed, not scored.
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from rule_score import score

from cardcost.advisor import Advisor
from cardcost.fees import read_fees
from cardcost.models import Scenario
from cardcost.numbers import find_numbers

ROOT = Path(__file__).resolve().parent.parent
GATE = 0.9
FEES = [ROOT / "samples/fees.json", ROOT / "catalog/fees.json"]
EXPECTS = {
    "expected_cost": "cost",
    "expected_ranking": "ranking",
    "expected_fact": "fact",
    "expected_question": "question",
}


def _dec(v: str | None) -> Decimal | None:
    return None if v is None else Decimal(v)


def extracted_rules(paths: list[Path], cards: set[str]) -> dict[str, list[dict]]:
    """Product label -> its stored rules, for the golden's cards only (other cards are not under test)."""
    out: dict[str, list[dict]] = {}
    for path in paths:
        for card, entry in (json.loads(path.read_text()) if path.exists() else {}).items():
            for fee in entry["fees"] if card in cards else []:
                out[card + (f":{fee['product']}" if fee["product"] else "")] = fee.get("rules", [])
    return out


def rule_numbers(rule: dict) -> list[Decimal]:
    nums = [*(rule["price"] or {}).values(), *[v for k, v in (rule.get("allowance") or {}).items() if k != "period"]]
    return [Decimal(str(v)) for v in nums if v is not None]


def run(golden: dict, fees, rules: dict[str, list[dict]]) -> tuple[dict, list[str], list[str]]:
    expected = golden["rules"]
    countries = [q["scenario"].get("country", "DE") for q in golden["questions"]]
    result = score(expected, rules, countries)
    failures = [f"extraction missing {label} {event}: {r.get('id')} {r['price']}" for label, event, r in result.missing]
    failures += [f"extraction extra {label} {event}: {r.get('name')} {r['price']}" for label, event, r in result.extra]
    hits = {k: [0, 0] for k in EXPECTS.values()}
    advisor = Advisor(fees, wallet=golden["wallet"])
    pending = []
    for q in golden["questions"]:
        if q.get("pending"):
            pending.append(f"{q['id']} ({q['pending']})")
            continue
        expect = next(v for k, v in EXPECTS.items() if k in q)
        advisor.wallet = q.get("wallet", golden["wallet"])
        hits[expect][1] += 1
        label = q["card"] + (f":{q['product']}" if q["product"] else "")
        if expect == "fact":
            fact = q["expected_fact"]
            got = result.found.get(fact["rule"])
            ok = got is not None and find_numbers(fact["answer"])[0] in rule_numbers(got)
            hits["fact"][0] += ok
            if not ok:
                failures.append(
                    f"{q['id']} fact {fact['rule']}: want {fact['answer']}, got {got and rule_numbers(got)}"
                )
            continue
        if expect == "question":
            # shortcut: the advisor cannot ask back yet, so every expected question is a miss until #9 adds it
            failures.append(f"{q['id']} question: want {q['expected_question']}, got an answer")
            continue
        try:
            table = advisor.cost_table(q["question"], Scenario(**q["scenario"]))
        except Exception as e:  # noqa: BLE001 - an eval must report, not crash
            failures.append(f"{q['id']} pipeline error: {e!r}")
            continue
        if expect == "cost":  # one-card question: only that card's cost counts
            got = next((ln.total for ln in table if ln.label == label), "missing")
            ok = got == _dec(q["expected_cost"])
            hits["cost"][0] += ok
            if not ok:
                failures.append(f"{q['id']} cost {label}: want {q['expected_cost']}, got {got}")
        else:
            ranking = [line.label for line in table]
            ok = ranking == q["expected_ranking"]
            hits["ranking"][0] += ok
            if not ok:
                failures.append(f"{q['id']} ranking: want {q['expected_ranking']}, got {ranking}")
    scores = {"recall": result.recall, "precision": result.precision}
    scores |= {k: v[0] / v[1] if v[1] else float("nan") for k, v in hits.items()}
    return scores, failures, pending


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", type=Path, default=ROOT / "evals/golden.json")
    args = ap.parse_args()
    golden = json.loads(args.golden.read_text())
    paths = [p for p in FEES if p.exists()]
    rules = extracted_rules(paths, {label.partition(":")[0] for label in golden["rules"]})
    scores, failures, pending = run(golden, read_fees(paths), rules)
    print(" ".join(f"{n:>10}" for n in scores))
    print(" ".join(f"{s:>10.2f}" for s in scores.values()))
    print(f"\n{len(failures)} failures:" if failures else "\nno failures")
    for f in failures:
        print("  " + f)
    if pending:
        print(f"\n{len(pending)} pending, not scored: " + ", ".join(pending))
    bad = [n for n in ("recall", "precision") if scores[n] < GATE]
    if bad:
        print("\nFAIL: " + ", ".join(f"{n} {scores[n]:.2f}" for n in bad) + f" < {GATE}")
    return bool(bad)


if __name__ == "__main__":
    sys.exit(main())
