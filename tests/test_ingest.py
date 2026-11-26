from pathlib import Path

from cardcost.ingest import read_text

ROOT = Path(__file__).parent.parent
CATALOG = sorted((ROOT / "catalog/docs").glob("*.pdf"))


def _page(name: str, n: int) -> str:
    return read_text(ROOT / "catalog/docs" / name)[n - 1]


def test_layout_box_is_read_as_prose_not_table():
    # pdfplumber sees the whole ING page as one "table" whose cells drop the row labels
    page2 = _page("ing.pdf", 2)
    assert "VISA Card [Debitkarte]" in page2 and "Bargeldauszahlungen" in page2


def test_overlapping_kerning_spaces_are_dropped():
    # ING's PDF places space glyphs on top of the next letter: "Aus lands einsatz entgelt"
    page2 = _page("ing.pdf", 2)
    assert "Auslandseinsatzentgelt" in page2 and "Aus lands" not in page2
    assert "Bargeldauszahlungen, an allen Geldautomaten" in page2  # real spaces stay


def test_two_column_page_is_read_column_by_column():
    page5 = _page("hvb.pdf", 5)
    assert "– an allen anderen Geldautomaten 2% mind. 5 EUR" in page5.splitlines()
    # label/value layouts are not split: ING keeps label and fee on one line
    assert "bei Casinobetrieben, Lotteriegesellschaften und Wettbüros: | 3,00 % vom Umsatz" in "\n".join(
        read_text(ROOT / "catalog/docs/ing.pdf")
    )
    # fee tables with a central gutter (C24, DKB) stay tables
    assert "Mit der C24 Mastercard (kostenlos) | 4 x 0,00 EUR 7 | 20 x 0,00 EUR 7" in _page("c24.pdf", 3)


def test_full_width_heading_on_column_page_stays_whole():
    page5 = _page("hvb.pdf", 5)
    assert "für Verbraucher und Nichtverbraucher bei Zahlungsdiensten (Bargeldauszahlung, Überweisung," in page5
    assert "\nSe\n" not in page5


def test_column_split_decisions_are_pinned():
    # shortcut thresholds in _columns were fitted on these PDFs; a change to them must show up here
    import pdfplumber

    from cardcost.ingest import _columns, _drop_kerning_spaces

    split = {}
    for path in CATALOG:
        with pdfplumber.open(path) as pdf:
            pages = [i + 1 for i, p in enumerate(pdf.pages) if len(_columns(_drop_kerning_spaces(p))) > 1]
        if pages:
            split[path.name] = pages
    assert split == {
        "bbva.pdf": [3],
        "consorsbank.pdf": [3],
        "hvb.pdf": [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12],
        "traderepublik.pdf": [1],
    }


def test_read_text_drops_control_characters(tmp_path):
    import hashlib

    from cardcost.ingest import READER_VERSION

    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"x")
    header = f"<!-- cardcost text: sha256={hashlib.sha256(b'x').hexdigest()} reader={READER_VERSION} -->"
    pdf.with_suffix(".md").write_text(f"{header}\n<!-- page 1 -->\n| \x07Auf den Betrag 2,20 %\n")
    assert read_text(pdf) == ["| Auf den Betrag 2,20 %"]
