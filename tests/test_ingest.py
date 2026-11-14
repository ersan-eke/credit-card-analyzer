import unicodedata
from pathlib import Path

from cardcost.ingest import chunk_lines, ingest_paths, passages_from_pages

ROOT = Path(__file__).parent.parent
SAMPLES = sorted((ROOT / "samples").glob("*.pdf"))
CATALOG = sorted((ROOT / "catalog/docs").glob("*.pdf"))


def test_nfc_and_page_metadata():
    decomposed = unicodedata.normalize("NFD", "Gebühr für Fremdwährung")
    ps = passages_from_pages("x", "x.pdf", ["erste Seite", decomposed])
    assert [p.page for p in ps] == [1, 2]
    assert ps[1].text == "Gebühr für Fremdwährung"
    assert unicodedata.is_normalized("NFC", ps[1].text)


def test_windows_size_and_overlap():
    lines = [" ".join(f"w{i}_{j}" for j in range(10)) for i in range(60)]  # 600 words
    chunks = chunk_lines(lines)
    sizes = [len(c.split()) for c in chunks]
    assert all(150 <= s <= 250 for s in sizes[:-1]) and sizes[-1] <= 250
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert a.splitlines()[-1] in b  # overlap carries the last line(s)


def test_sample_ingest_never_mixes_files_and_renders_tables():
    ps = ingest_paths(SAMPLES)
    assert {"alpha_card", "beta_card", "gamma_card"} <= {p.card_id for p in ps}
    for p in ps:
        assert p.file == f"{p.card_id}.pdf"
    beta_p1 = " ".join(p.text for p in ps if p.card_id == "beta_card" and p.page == 1)
    assert "Bargeldauszahlung am Geldautomaten | 3,0 % mind. 6,00 EUR | 1,0 % mind. 7,50 EUR" in beta_p1


def test_layout_box_is_read_as_prose_not_table():
    # pdfplumber sees the whole ING page as one "table" whose cells drop the row labels
    ps = ingest_paths([p for p in CATALOG if p.name == "ing.pdf"])
    page2 = " ".join(p.text for p in ps if p.page == 2)
    assert "VISA Card [Debitkarte]" in page2 and "Bargeldauszahlungen" in page2


def test_overlapping_kerning_spaces_are_dropped():
    # ING's PDF places space glyphs on top of the next letter: "Aus lands einsatz entgelt"
    ps = ingest_paths([p for p in CATALOG if p.name == "ing.pdf"])
    page2 = " ".join(p.text for p in ps if p.page == 2)
    assert "Auslandseinsatzentgelt" in page2 and "Aus lands" not in page2
    assert "Bargeldauszahlungen, an allen Geldautomaten" in page2  # real spaces stay


def test_two_column_page_is_read_column_by_column():
    hvb = ingest_paths([p for p in CATALOG if p.name == "hvb.pdf"])
    page5 = "\n".join(p.text for p in hvb if p.page == 5)
    assert "– an allen anderen Geldautomaten 2% mind. 5 EUR" in page5.splitlines()
    # label/value layouts are not split: ING keeps label and fee on one line
    ing = ingest_paths([p for p in CATALOG if p.name == "ing.pdf"])
    assert any("bei Casinobetrieben, Lotteriegesellschaften und Wettbüros: | 3,00 % vom Umsatz" in p.text for p in ing)
    # fee tables with a central gutter (C24, DKB) stay tables
    c24 = ingest_paths([p for p in CATALOG if p.name == "c24.pdf"])
    row = "Mit der C24 Mastercard (kostenlos) | 4 x 0,00 EUR 7 | 20 x 0,00 EUR 7"
    assert any(row in p.text for p in c24 if p.page == 3)


def test_full_width_heading_on_column_page_stays_whole():
    hvb = ingest_paths([p for p in CATALOG if p.name == "hvb.pdf"])
    page5 = "\n".join(p.text for p in hvb if p.page == 5)
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
