"""Offline estimate per catalog price list: views, keyword-routed and triaged views, and input tokens for the
document call, the route calls and the triage calls. Never calls a model; counts only, no rule text.

    uv run python evals/section_stats.py
"""

import json

from cardcost.assemble import Document
from cardcost.extract import (
    CHARS_PER_TOKEN,
    DOC_SYSTEM,
    DOC_TOOL,
    ROUTE_SYSTEMS,
    ROUTE_TOOLS,
    TRIAGE_SYSTEM,
    TRIAGE_TOOL,
    _document_prompt,
    _path,
    _repeated,
    _section_prompt,
)
from cardcost.fees import CATALOG_DOCS
from cardcost.ingest import read_text
from cardcost.routes import ROUTES, route
from cardcost.sections import layout, views


def _tokens(*parts: str) -> int:
    return sum(len(p) for p in parts) // CHARS_PER_TOKEN


def stats(card: str, pages: list[str]) -> dict:
    lay = layout(pages)
    # the empty Document is a stand-in: the real message adds the card and condition lists
    empty = Document([], [], None, {})
    fixed = {r: _tokens(ROUTE_SYSTEMS[r], json.dumps(ROUTE_TOOLS[r])) for r in ROUTES}
    triage_fixed = _tokens(TRIAGE_SYSTEM, json.dumps(TRIAGE_TOOL))
    sent: set = set()
    all_views = [v for s in lay.sections for v in views(s, lay) if not _repeated(v, sent)]
    out = dict.fromkeys(("example", "routed", "triage", "route_calls", "route_tokens", "triage_tokens"), 0)
    out["triage_route_tokens"] = 0
    for v in all_views:
        r = route(v, lay)
        if r.example:
            out["example"] += 1
            continue
        out["routed"] += bool(r.routes)
        out["route_calls"] += len(r.routes)
        out["route_tokens"] += sum(fixed[x] + _tokens(_section_prompt(card, v, empty, lay, x)) for x in r.routes)
        if r.triage:
            out["triage"] += 1
            out["triage_tokens"] += triage_fixed + _tokens(v.text, _path(v, lay))
            out["triage_route_tokens"] += fixed["cash"] + _tokens(_section_prompt(card, v, empty, lay, "cash"))
    return out | {
        "sections": len(lay.sections),
        "views": len(all_views),
        "doc_tokens": _tokens(DOC_SYSTEM, json.dumps(DOC_TOOL), _document_prompt(card, lay)),
    }


COLS = (
    "sections",
    "views",
    "example",
    "routed",
    "triage",
    "route_calls",
    "doc_tokens",
    "route_tokens",
    "triage_tokens",
    "triage_route_tokens",
)


def main() -> int:
    total = dict.fromkeys(COLS, 0)
    print(f"{'card':28}" + "".join(f" {c:>{max(len(c), 6)}}" for c in COLS))
    row = lambda name, s: print(f"{name:28}" + "".join(f" {s[c]:>{max(len(c), 6)}}" for c in COLS))  # noqa: E731
    for path in sorted(CATALOG_DOCS.glob("*.pdf")):
        s = stats(path.stem, read_text(path))
        total = {k: total[k] + s[k] for k in total}
        row(path.stem, s)
    row("TOTAL", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
