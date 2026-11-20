"""Score extraction (recall and precision of rules), cost (one-card questions), ranking (comparisons), facts (a stated
fee or count) and questions back (the advisor should ask instead of answering). All of it is read from the committed
fees files (samples/fees.json, catalog/fees.json), so it needs no LLM and no embedding model.

uv run python evals/run_eval.py
uv run python evals/run_eval.py --golden evals/golden_real.json   # the real price lists
uv run python evals/run_eval.py --golden evals/golden_real.json --fees out.json   # a fresh extraction
Exit 1 if rule recall or precision < 0.9. Questions marked `pending` name the ticket whose calculator they wait for and
are listed, not scored.
"""

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

from rule_score import score, tally

from cardcost import extract
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


HISTORY = ROOT / "evals/prompt_scores.md"
HISTORY_HEAD = (
    "# Prompt score history\n\nPredictions per failure class are written here before each run.\n\n"
    "| version | golden | schema | temp | tokens in/out | all | dev | holdout | no examples | no example banks "
    "| empty lists | missing | extra | notes |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
)


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


def _bank(label: str) -> str:
    return label.partition(":")[0].split("_")[0]


def sha8(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def views(golden: dict, s) -> dict[str, tuple[float, float]]:
    """(recall, precision) of one score over all golden rules, dev banks, holdout banks, without the rules the prompt
    quotes as examples, and without every bank that supplied an example (decisions 5, 10)."""
    holdout = set(golden.get("holdout", []))
    flagged = [(label, r["id"]) for label, rules in golden["rules"].items() for r in rules if r.get("used_as_example")]
    ids, banks = {i for _, i in flagged}, {_bank(label) for label, _ in flagged}
    return {
        "all": tally(s, lambda label, i: True),
        "dev": tally(s, lambda label, i: _bank(label) not in holdout),
        "holdout": tally(s, lambda label, i: _bank(label) in holdout),
        "no_examples": tally(s, lambda label, i: i not in ids),
        "no_example_banks": tally(s, lambda label, i: _bank(label) not in banks),
    }


def empty_lists(golden: dict, rules: dict) -> list[str]:
    """Golden cards (price lists) with no extracted product at all."""
    return sorted({label.partition(":")[0] for label in golden["rules"]} - {label.partition(":")[0] for label in rules})


def label_diff(golden: dict, rules: dict) -> tuple[list[str], list[str]]:
    """Extracted labels the golden does not have, golden labels never extracted."""
    return sorted(set(rules) - set(golden["rules"])), sorted(set(golden["rules"]) - set(rules))


def history_row(version, golden_path, vs, empty, tokens, extra, missing) -> str:
    cells = [
        version,
        sha8(Path(golden_path).read_bytes()),
        sha8(json.dumps(extract.TOOL, sort_keys=True).encode()),
        str(getattr(extract, "TEMPERATURE", None)),
        f"{tokens[0]}/{tokens[1]}",
        *(f"{r:.2f}/{p:.2f}" for r, p in vs.values()),
        f"{len(empty)}: {' '.join(empty)}" if empty else "0",
        str(missing),
        str(extra),
        "",
    ]
    return "| " + " | ".join(cells) + " |"


def run_tokens(path: Path | None) -> tuple[int, int]:
    """Input and output tokens summed over the recorded responses of a run."""
    calls = json.loads(path.read_text()).values() if path and path.exists() else []
    return sum(c["usage"]["input_tokens"] for c in calls), sum(c["usage"]["output_tokens"] for c in calls)


def run(golden: dict, fees, rules: dict[str, list[dict]]):
    expected = golden["rules"]
    countries = [q["scenario"].get("country", "DE") for q in golden["questions"]]
    scored = set(golden["scored_products"]) if "scored_products" in golden else None
    result = score(expected, rules, countries, scored)
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
    return scores, failures, pending, result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", type=Path, default=ROOT / "evals/golden.json")
    ap.add_argument("--record", metavar="VERSION", help="append this run's row to evals/prompt_scores.md")
    ap.add_argument("--runs", type=Path, help="recorded responses of the run, for the token counts of the row")
    ap.add_argument("--fees", type=Path, nargs="*", help="fees files to score (default: samples and catalog)")
    args = ap.parse_args()
    golden = json.loads(args.golden.read_text())
    paths = [p for p in args.fees or FEES if p.exists()]
    rules = extracted_rules(paths, {label.partition(":")[0] for label in golden["rules"]})
    scores, failures, pending, result = run(golden, read_fees(paths), rules)
    print(" ".join(f"{n:>10}" for n in scores))
    print(" ".join(f"{s:>10.2f}" for s in scores.values()))
    vs = views(golden, result)
    print("\n" + "\n".join(f"{k:<17} recall {r:.2f}  precision {p:.2f}" for k, (r, p) in vs.items()))
    empty = empty_lists(golden, rules)
    total = len({label.partition(":")[0] for label in golden["rules"]})
    print(f"{len(empty)} of {total} lists returned nothing" + (": " + ", ".join(empty) if empty else ""))
    extra_labels, never = label_diff(golden, rules)
    print(f"extracted, not in golden: {extra_labels}\ngolden, never extracted: {never}")
    print(f"\n{len(failures)} failures:" if failures else "\nno failures")
    for f in failures:
        print("  " + f)
    if pending:
        print(f"\n{len(pending)} pending, not scored: " + ", ".join(pending))
    if args.record:
        row = history_row(
            args.record, args.golden, vs, empty, run_tokens(args.runs), len(result.extra), len(result.missing)
        )
        if not HISTORY.exists():
            HISTORY.write_text(HISTORY_HEAD)
        with HISTORY.open("a") as f:
            f.write(row + "\n")
    bad = [n for n in ("recall", "precision") if scores[n] < GATE]
    if bad:
        print("\nFAIL: " + ", ".join(f"{n} {scores[n]:.2f}" for n in bad) + f" < {GATE}")
    return bool(bad)


if __name__ == "__main__":
    sys.exit(main())
