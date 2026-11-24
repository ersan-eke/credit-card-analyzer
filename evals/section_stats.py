"""Offline estimate per catalog price list: sections, section views and input tokens for the document call and, as
an upper bound (every view sent but a repeat), the section calls. Never calls a model; counts only, no rule text.

    uv run python evals/section_stats.py
"""

import json

from cardcost.assemble import Document
from cardcost.extract import (
    CHARS_PER_TOKEN,
    DOC_SYSTEM,
    DOC_TOOL,
    SECTION_SYSTEM,
    SECTION_TOOL,
    _document_prompt,
    _repeated,
    _section_prompt,
)
from cardcost.fees import CATALOG_DOCS
from cardcost.ingest import read_text
from cardcost.sections import layout, views


def _tokens(*parts: str) -> int:
    return sum(len(p) for p in parts) // CHARS_PER_TOKEN


def stats(card: str, pages: list[str]) -> dict:
    lay = layout(pages)
    fixed = _tokens(SECTION_SYSTEM, json.dumps(SECTION_TOOL))
    # the empty Document is an upper bound's stand-in: the real message adds the card and condition lists
    empty = Document([], [], None, {})
    sent: set = set()
    all_views = [v for s in lay.sections for v in views(s, lay) if not _repeated(v, sent)]
    return {
        "sections": len(lay.sections),
        "views": len(all_views),
        "doc_tokens": _tokens(DOC_SYSTEM, json.dumps(DOC_TOOL), _document_prompt(card, lay)),
        "section_tokens": sum(fixed + _tokens(_section_prompt(card, v, empty, lay)) for v in all_views),
    }


def main() -> int:
    total = dict.fromkeys(("sections", "views", "doc_tokens", "section_tokens"), 0)
    print(f"{'card':28} {'sections':>8} {'views':>6} {'doc_tokens':>10} {'section_tokens':>14}")
    for path in sorted(CATALOG_DOCS.glob("*.pdf")):
        s = stats(path.stem, read_text(path))
        total = {k: total[k] + s[k] for k in total}
        print(f"{path.stem:28} {s['sections']:8} {s['views']:6} {s['doc_tokens']:10} {s['section_tokens']:14}")
    t = total
    print(f"{'TOTAL':28} {t['sections']:8} {t['views']:6} {t['doc_tokens']:10} {t['section_tokens']:14}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
