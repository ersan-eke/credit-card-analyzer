import functools
import hashlib
import logging
import re
from pathlib import Path

import pdfplumber
import pypdfium2

log = logging.getLogger("cardcost.ingest")
# Bump when convert() changes, so cached text is converted again.
READER_VERSION = "docling+pdfplumber 1"


def _is_data_table(page, table) -> bool:
    """A layout box detected as a table loses its label text in extract(); read those as prose instead."""
    cell_words = sum(len((c or "").split()) for row in table.extract() for c in row)
    region_words = len((page.crop(table.bbox).extract_text() or "").split())
    return cell_words >= 0.8 * region_words


def _drop_kerning_spaces(page):
    """ING puts space glyphs on top of the next letter: "Aus lands einsatz entgelt"; real spaces end first."""
    chars = page.chars
    kerned = {
        (c["x0"], c["top"])
        for c, nxt in zip(chars, chars[1:], strict=False)
        if c["text"] == " " and abs(nxt["top"] - c["top"]) <= 1 and nxt["x0"] < c["x1"] - 0.5
    }
    return page.filter(
        lambda o: not (o.get("object_type") == "char" and o["text"] == " " and (o["x0"], o["top"]) in kerned)
    )


def _page_text(page) -> str:
    """Prose outside tables, then each table as 'cell | cell' rows so columns stay attached to products."""
    tables = [t for t in page.find_tables() if _is_data_table(page, t)]
    outside = page
    for t in tables:
        outside = outside.outside_bbox(t.bbox)
    rows = [" | ".join((c or "").replace("\n", " ") for c in row) for t in tables for row in t.extract()]
    return "\n".join([outside.extract_text() or "", *rows])


_VALUE = re.compile(r"\d|EUR|€|%|kostenlos|kostenfrei")


def _columns(page) -> list:
    """Two text columns (HVB) interleave line by line in extract_text(); split them at a clear central gutter.
    Label/value layouts can have a gutter too, but their right side is mostly fee values, so they stay whole."""
    words, width = page.extract_words(), page.width
    if not words:
        return [page]
    gutter = min(
        (width * 0.45 + 2 * i for i in range(int(width * 0.12 / 2))),
        key=lambda x: sum(w["x0"] < x < w["x1"] for w in words),
    )
    crossing = sum(w["x0"] < gutter < w["x1"] for w in words)
    left = sum(w["x1"] <= gutter for w in words) / len(words)
    right = [w for w in words if w["x0"] >= gutter]
    values = sum(bool(_VALUE.search(w["text"])) for w in right) / max(len(right), 1)
    # shortcut: thresholds fitted on six price lists (HVB columns <= 0.25 values, DKB/C24 fee layouts >= 0.32)
    if crossing > 0.02 * len(words) or not 0.4 <= left <= 0.62 or values >= 0.3:
        return [page]
    # words across the gutter belong to full-width lines (headings): read those whole, and keep them out of both columns
    bands = [(w["top"] - 1, w["bottom"] + 1) for w in words if w["x0"] < gutter < w["x1"]]

    def in_band(o) -> bool:
        return o.get("object_type") == "char" and any(t <= o["top"] and o["bottom"] <= b for t, b in bands)

    columns = [
        page.crop(box).filter(lambda o: not in_band(o))
        for box in ((0, 0, gutter, page.height), (gutter, 0, width, page.height))
    ]
    return ([page.filter(in_band)] if bands else []) + columns


def read_pdf(path: Path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return ["\n".join(_page_text(c) for c in _columns(_drop_kerning_spaces(p))) for p in pdf.pages]


@functools.cache
def _docling():
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling_core.types.doc import ContentLayer
    except ImportError as e:
        raise RuntimeError("converting a price list needs the layout extractor: uv sync --extra ingest") from e
    options = PdfFormatOption(pipeline_options=PdfPipelineOptions(do_ocr=False))
    # headers and footers too, so no number of the PDF is lost
    return DocumentConverter(format_options={InputFormat.PDF: options}), {ContentLayer.BODY, ContentLayer.FURNITURE}


def convert(path: Path) -> list[str]:
    """Each page as Markdown with tables intact (Docling, ADR 0003). A page Docling finds no table on that is set in
    two text columns (HVB's label/value pages) is read by read_pdf's column split, which keeps fees next to labels."""
    converter, layers = _docling()
    doc = converter.convert(str(path)).document
    table_pages = {p.page_no for t in doc.tables for p in t.prov}
    out = []
    with pdfplumber.open(path) as pdf:
        for n, page in enumerate(pdf.pages, start=1):
            columns = _columns(_drop_kerning_spaces(page))
            if n not in table_pages and len(columns) > 1:
                out.append("\n".join(_page_text(c) for c in columns))
            else:
                md = doc.export_to_markdown(page_no=n, included_content_layers=layers)
                out.append(re.sub(r"-{3,}", "---", re.sub(r" {2,}", " ", md)))  # drop table padding
    return [page.replace("\xad", "") for page in out]  # soft hyphens would split words for search and quotes


_PAGE = re.compile(r"^<!-- page \d+ -->$", re.M)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f]")  # glyph artifacts the model cannot copy into a quote


def read_text(path: Path) -> list[str]:
    """The price list's pages as converted text, cached beside the PDF (<id>.md, reviewed with the fees) and reused
    while the PDF and the reader are unchanged."""
    cache = path.with_suffix(".md")
    header = f"<!-- cardcost text: sha256={hashlib.sha256(path.read_bytes()).hexdigest()} reader={READER_VERSION} -->"
    if cache.exists():
        first, _, body = cache.read_text().partition("\n")
        if first == header:
            return [_CONTROL.sub("", page).strip("\n") for page in _PAGE.split(body)[1:]]
    pages = convert(path)
    cache.write_text(header + "\n" + "".join(f"<!-- page {n} -->\n{t}\n" for n, t in enumerate(pages, start=1)))
    return [_CONTROL.sub("", page) for page in pages]


_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def lost_numbers(path: Path, pages: list[str]) -> list[str]:
    """Numbers in the PDF's text layer that the converted text lacks as a whole number ("2,90" is not kept by "12,90").
    Read through pdfplumber and through pdfium, because each garbles a few glyph layouts its own way (pdfplumber
    interleaves DKB's overlapping footer copies into "22 vvoonn 66", pdfium glues C24's footnote marks to the next cell
    as "27,49"); a number the conversion lost is missing under both. Rotated text is skipped: margin form codes, read
    backwards by pdfplumber."""
    with pdfplumber.open(path) as pdf:
        plumber = " ".join(p.filter(lambda o: o.get("upright", True)).extract_text() or "" for p in pdf.pages)
    pdf = pypdfium2.PdfDocument(path)
    try:
        pdfium = " ".join(page.get_textpage().get_text_bounded() for page in pdf)
    finally:
        pdf.close()
    text = "\n".join(pages)
    found = set(_NUMBER.findall(text))
    squeezed = re.sub(r"\s+", "", text)  # a number the conversion split by spacing ("04 03 07") still counts

    def kept(n: str) -> bool:
        return n in found or re.search(rf"(?<![\d.,]){re.escape(n)}(?![\d]|[.,]\d)", squeezed) is not None

    lost = [{n for n in _NUMBER.findall(raw) if not kept(n)} for raw in (plumber, pdfium)]
    return sorted(lost[0] & lost[1])


def process_job(conn, job_id: int) -> str:
    """Parse a queued document; on success the file can be passed to `cardcost ingest`."""
    row = conn.execute("SELECT path FROM ingest_job WHERE id = ?", (job_id,)).fetchone()
    try:
        n = len(read_pdf(Path(row["path"])))  # a parse check only; conversion needs the ingest extra
        status = "done" if n else "failed"
    except Exception:  # noqa: BLE001 - a broken PDF must mark the job, not kill the worker
        log.exception("ingest_failed", extra={"job_id": job_id})
        status = "failed"
    with conn:
        conn.execute("UPDATE ingest_job SET status = ? WHERE id = ?", (status, job_id))
    return status
