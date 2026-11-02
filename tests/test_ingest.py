import unicodedata
from pathlib import Path

from cardcost.ingest import chunk_lines, ingest_paths, passages_from_pages

SAMPLES = sorted((Path(__file__).parent.parent / "samples").glob("*.pdf"))


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
