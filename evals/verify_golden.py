"""Verification sheet for a golden file: for every expected number, the lines on its expected PDF page that contain it.

Reads the PDFs with plain pdfplumber extract_text(), not cardcost's ingest, so an ingest bug cannot hide here.
uv run python evals/verify_golden.py evals/golden_real.json > evals/golden_real_sheet.md
"""

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import pdfplumber

from cardcost.models import FREE_WORDS
from cardcost.numbers import find_numbers

ROOT = Path(__file__).resolve().parent.parent
FEE_LINE = re.compile(r"Geldautomat|Bargeld|Abhebung|Fremdwährung|Währung|Auslands|Wechsel|Karte", re.IGNORECASE)


# words that tie a line to the field being checked; lines with them are listed first
FIELD_WORDS = {
    "fx": re.compile(r"Fremdwährung|Währung|Auslands|Wechsel", re.IGNORECASE),
    "cash": re.compile(r"Geldautomat|Abhebung|Bargeldauszahlung|weitere", re.IGNORECASE),
}


def lines_with(field: str, value: Decimal, lines: list[str]) -> list[str]:
    """Matching lines as 'previous line ⏎ line': PDF text often puts the label on the line before the fee."""
    found = []
    for prev, ln in zip(["", *lines], lines, strict=False):
        context = f"{prev} ⏎ {ln}" if prev else ln
        if value == 0:  # "kostenlos" counts as 0, but only next to a fee word, or every page would match
            ok = (FREE_WORDS.search(ln) or value in find_numbers(ln)) and FEE_LINE.search(context)
        else:
            ok = value in find_numbers(ln)
        if ok:
            found.append(context)
    words = FIELD_WORDS["fx" if field.startswith("fx") else "cash"]
    return sorted(found, key=lambda c: not words.search(c))  # stable: page order within each group


def sheet(golden: dict) -> tuple[str, int]:
    out, missing = [f"# Verification sheet\n\n{golden['_note']}\n"], 0
    for q in golden["questions"]:
        verify = "VERIFY" in q["_hand"]
        out.append(f"## {q['id']}{' (VERIFY)' if verify else ''}: {q['question']}\n")
        label = q["card"] + (f":{q['product']}" if q["product"] else "")
        out.append(f"`{label}`, page {q['expected_page']}. Hand: {q['_hand']}\n")
        want = (
            f"cost {q['expected_cost']} EUR" if "expected_cost" in q else "ranking " + " > ".join(q["expected_ranking"])
        )
        out.append(f"Expected {want}\n")
        lines = []
        if q["expected_page"]:
            with pdfplumber.open(ROOT / "samples" / f"{q['card']}.pdf") as pdf:
                lines = (pdf.pages[q["expected_page"] - 1].extract_text() or "").splitlines()
        for field, raw in q["expected_fields"].items():
            if raw is None:
                out.append(f"- `{field}` = null: check the page states no number for it")
                continue
            found = lines_with(field, Decimal(raw), lines)
            missing += not found
            out.append(f"- `{field}` = {raw}: " + ("**NOT FOUND on this page**" if not found else ""))
            out += [f"  - `{ln.strip()}`" for ln in found[:6]]
        out.append("")
    return "\n".join(out), missing


def main() -> int:
    text, missing = sheet(json.loads(Path(sys.argv[1]).read_text()))
    print(text)
    print(f"\n{missing} expected value(s) not found on their page.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
