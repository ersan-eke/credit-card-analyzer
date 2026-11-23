"""Cut a price list into small price sections by its layout (headings, tables), without a model."""

import re
from typing import NamedTuple

from cardcost.models import FREE_WORDS

MAX_LINES = 40
PRICE = re.compile(rf"\d(?:[\d.,]*\d)?\s*(?:€|EUR\b|%)|€\s*\d|\d,-|(?i:{FREE_WORDS.pattern})")
# "3 ", "1.2 ", "a) ", "II. ", "B. " followed by a word
NUMBERING = re.compile(
    r"(?:(?P<roman>[IVX]+\.)|(?P<upper>[A-Z]\.)|(?P<digits>\d+(?:\.\d+)*\.?)|(?P<lower>[a-z]\)))\s+[^\W\d_]"
)
TABLE_RULE = re.compile(r"\|\s*:?-{3,}")


class Section(NamedTuple):
    id: str  # f"p{page}.{start}"
    page: int  # 1-based
    start: int  # index of lines[0] in pages[page - 1].splitlines()
    lines: list[str]  # verbatim page lines, consecutive
    headings: list[int]  # ids into Layout.headings, outermost first; [] if none above
    table: int | None  # id into Layout.tables when the section's rows belong to a markdown table


class Layout(NamedTuple):
    headings: list[str]  # heading text, document order
    tables: list[list[str]]  # header cells per table (label column first)
    sections: list[Section]


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _rank(text: str) -> tuple:
    """Nesting rank of a heading: markdown levels outermost, then numbering styles, then table headings."""
    if text.startswith("#"):
        return (0, len(text) - len(text.lstrip("#")))
    if m := NUMBERING.match(text):
        if m["digits"]:
            return (1, 2 + m["digits"].rstrip(".").count("."))
        return (1, {"upper": 0, "roman": 1, "lower": 9}[m.lastgroup])
    return (2,)


def _ids(path: dict[tuple, int]) -> list[int]:
    return [path[r] for r in sorted(path)]


def _split(lines: list[str], start: int, end: int, max_lines: int) -> list[tuple[int, int]]:
    """[start, end) cut into runs of at most max_lines, each ending on its last price line."""
    runs = []
    while start < end:
        stop = end
        if end - start > max_lines:
            # cut after a price line or at a blank line, so lead-in prose stays with its price
            cuts = [
                c for c in range(start + 1, start + max_lines + 1) if PRICE.search(lines[c - 1]) or not lines[c].strip()
            ]
            stop = cuts[-1] if cuts else start + max_lines
        prices = [i for i in range(start, stop) if PRICE.search(lines[i])]
        if prices:
            runs.append((start, prices[-1] + 1))
        # lines after the last price go on with the next run; a run never opens on a blank line
        start = prices[-1] + 1 if prices else stop
        while start < end and not lines[start].strip():
            start += 1
    return runs


def layout(pages: list[str], max_lines: int = MAX_LINES) -> Layout:
    headings: list[str] = []
    tables: list[list[str]] = []
    sections: list[Section] = []
    path: dict[tuple, int] = {}  # rank -> heading id, the headings above the current line

    for page_no, page in enumerate(pages, 1):
        lines = page.splitlines()
        runs = []  # (start, price line indexes, heading ids, table) between two boundaries
        table = None
        start, prices = 0, []
        joining = False  # the previous line was a table heading row, so a wrapped one continues it
        for i, line in enumerate(lines):
            text = line.strip()
            in_table = text.startswith("|")
            if in_table and i + 1 < len(lines) and TABLE_RULE.match(lines[i + 1].strip()):
                runs.append((start, prices, _ids(path), table))
                tables.append(_cells(text))
                table, joining = len(tables) - 1, False
                # Docling may take the first price row as the header: then the header is content too
                start, prices = (i, [i]) if PRICE.search(text) else (i + 2, [])
                continue
            if not in_table and table is not None:  # the table ended: its headings and rows end with it
                runs.append((start, prices, _ids(path), table))
                table, start, prices = None, i, []
                path = {r: h for r, h in path.items() if r != (2,)}
            if in_table and i < start or text.startswith("<!--"):
                continue

            if PRICE.search(text):  # a price line is content, never a heading (Docling mislabels "## kostenfrei")
                heading = None
            elif in_table:
                cells = _cells(text)
                heading = cells[0] if cells[0] and not any(cells[1:]) else None
            elif text.startswith("#") or (NUMBERING.match(text) and len(text) < 120):
                heading = text
            else:
                heading = None

            if heading is None:
                joining = False
                if PRICE.search(line):
                    prices.append(i)
                continue
            if joining and not NUMBERING.match(heading):
                headings[-1] += " " + heading
            else:
                runs.append((start, prices, _ids(path), table))
                rank = _rank(heading)
                path = {r: h for r, h in path.items() if r < rank}
                path[rank] = len(headings)
                headings.append(heading)
            start, prices, joining = i + 1, [], in_table
        runs.append((start, prices, _ids(path), table))

        for start, prices, ids, table in runs:
            if prices:
                first = next(i for i in range(start, prices[0] + 1) if lines[i].strip())
                for a, b in _split(lines, first, prices[-1] + 1, max_lines):
                    sections.append(Section(f"p{page_no}.{a}", page_no, a, lines[a:b], ids, table))

    return Layout(headings, tables, sections)
