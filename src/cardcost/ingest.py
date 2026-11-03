import logging
import unicodedata
from collections.abc import Iterable
from pathlib import Path

import pdfplumber

from cardcost.models import Passage

log = logging.getLogger("cardcost.ingest")
TARGET_WORDS = 200
OVERLAP_WORDS = 30


def _words(lines: list[str]) -> int:
    return sum(len(line.split()) for line in lines)


def chunk_lines(lines: list[str], target: int = TARGET_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    """Group whole lines (keeps table rows intact) into ~target-word windows with ~overlap words carried."""
    # shortcut: a single line longer than ~250 words is not split; fine for fee reports, split words if needed.
    chunks: list[str] = []
    cur: list[str] = []
    fresh = False
    for line in lines:
        cur.append(line)
        fresh = True
        if _words(cur) >= target:
            chunks.append("\n".join(cur))
            tail: list[str] = []
            while _words(tail) < overlap and len(tail) < len(cur) - 1:
                tail.insert(0, cur[-len(tail) - 1])
            cur, fresh = tail, False
    if fresh:
        chunks.append("\n".join(cur))
    return chunks


def passages_from_pages(card_id: str, file: str, pages: list[str]) -> list[Passage]:
    out = []
    for page_no, text in enumerate(pages, start=1):
        lines = [ln.strip() for ln in unicodedata.normalize("NFC", text).splitlines() if ln.strip()]
        for i, chunk in enumerate(chunk_lines(lines)):
            out.append(Passage(id=f"{card_id}:p{page_no}:{i}", card_id=card_id, file=file, page=page_no, text=chunk))
    return out


def _is_data_table(page, table) -> bool:
    """A layout box detected as a table loses its label text in extract(); read those as prose instead."""
    cell_words = sum(len((c or "").split()) for row in table.extract() for c in row)
    region_words = len((page.crop(table.bbox).extract_text() or "").split())
    return cell_words >= 0.8 * region_words


def _page_text(page) -> str:
    """Prose outside tables, then each table as 'cell | cell' rows so columns stay attached to products."""
    tables = [t for t in page.find_tables() if _is_data_table(page, t)]
    outside = page
    for t in tables:
        outside = outside.outside_bbox(t.bbox)
    rows = [" | ".join((c or "").replace("\n", " ") for c in row) for t in tables for row in t.extract()]
    return "\n".join([outside.extract_text() or "", *rows])


def read_pdf(path: Path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [_page_text(p) for p in pdf.pages]


def ingest_paths(paths: Iterable[Path]) -> list[Passage]:
    out = []
    for path in paths:
        out += passages_from_pages(path.stem, path.name, read_pdf(path))
    return out


def process_job(conn, job_id: int) -> str:
    """Parse a queued document; on success it joins the corpus (see advisor.corpus_paths)."""
    row = conn.execute("SELECT path FROM ingest_job WHERE id = ?", (job_id,)).fetchone()
    try:
        n = len(ingest_paths([Path(row["path"])]))
        status = "done" if n else "failed"
    except Exception:  # noqa: BLE001 - a broken PDF must mark the job, not kill the worker
        log.exception("ingest_failed", extra={"job_id": job_id})
        status = "failed"
    with conn:
        conn.execute("UPDATE ingest_job SET status = ? WHERE id = ?", (status, job_id))
    return status
