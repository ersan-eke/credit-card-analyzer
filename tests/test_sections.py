import json
from decimal import Decimal
from pathlib import Path

import pytest

from cardcost.extract import _squash
from cardcost.ingest import read_text
from cardcost.sections import MAX_LINES, PRICE, Layout, Section, layout, views

ROOT = Path(__file__).parent.parent

# short literal page excerpts, copied from read_text() of the dev documents
C24_PAGE3 = """\
## B. Preise und Leistungsmerkmale bei Zahlungsdiensten für Privatkunden

| | C24 Smartkonto | C24 Pluskonto | C24 Maxkonto | C24 Basiskonto |
|---|---|---|---|---|
| I. Bargeldeinzahlungen und Bargeldauszahlungen | | | | |
| 1. Bargeldauszahlungen am | | | | |
| Geldautomaten 5 oder im | | | | |
| Partnergeschäft 6 in Euro (je | | | | |
| Kalendermonat) Mit der C24 Mastercard (kostenlos) | 4 x 0,00 EUR 7 | 20 x 0,00 EUR 7 | 20 x 0,00 EUR 7 | - |
| Jede weitere Bargeldauszahlung mit der C24 Mastercard | 2,00 EUR | 2,00 EUR | 2,00 EUR | 2,00 EUR |
| Jede weitere Bargeldauszahlung im Partnergeschäft 6 | 2,00 EUR | 2,00 EUR | 2,00 EUR | 2,00 EUR |
| Mit der C24 girocard | Der Automatenbetreiber erhebt ein direktes Entgelt für jede Bargeldauszahlung 5 | Der Automatenbetreiber erhebt ein direktes Entgelt für jede Bargeldauszahlung 5 | Der Automatenbetreiber erhebt ein direktes Entgelt für jede Bargeldauszahlung 5 | Der Automatenbetreiber erhebt ein direktes Entgelt für jede Bargeldauszahlung 5 |"""  # noqa: E501

CONSORS_DEBIT_TABLE = """\
| Visa Card Debit | Preis | Preis | Preis |
|---|---|---|---|
| Ausgabe einer Visa Card Debit für den oder die Kontoinhaber | kostenlos | kostenlos | - |
| Bargeldauszahlung an allen Visa-zugänglichen Geldausgabe automaten im EWR auf den jeweiligen, nicht auf Euro lautenden Auszahlungsbetrag | 2,10 % 2 | 2,10 % 2 | - |
| Bargeldauszahlung an allen Visa-zugänglichen Geldausgabeauto- maten außerhalb des EWR auf den jeweiligen Auszahlungsbetrag | 2,10 % 2 | 2,10 % 2 | - |"""  # noqa: E501

HVB_ATM = """\
3 Bargeldauszahlung mit der Kreditkarte am Geldautomaten
Hinweis: An Geldautomaten, die nicht von der UniCredit Group und nicht der
Cash Group im Inland betrieben werden, verlangt der Betreiber des
Geldautomaten ggf. ein zusätzliches Entgelt.
a) HVB Mastercard, HVB Mastercard Gold, HVB Visa Card, HVB Mastercard
Firmenkunden, HVB Mastercard Gold Firmenkunden, HVB Corporate Card
(jeweils Kreditkarte)
– Bargeldauszahlung mit der Kreditkarte am Geldautomaten innerhalb
der EU/EWR-Staaten in EUR
– an Geldautomaten der HypoVereinsbank kostenfrei
– an allen anderen Geldautomaten 2% mind. 5 EUR
Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold
im HVB ExklusivKonto, Depot Global, HVB Platinumkonto
(Hauptkonto) kostenfrei
Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold
im HVB AktivKonto und HVB PlusKonto 2,50 EUR
Stand: 01.11.2026
– Bargeldauszahlung mit der Kreditkarte an fremden
Geldautomaten in Fremdwährung (Umrechnungskurs
siehe Teil B, letztes Unterkapitel) 2% mind. 5 EUR
Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold
im HVB ExklusivKonto, Depot Global, HVB Platinumkonto
(Hauptkonto) kostenfrei
Ausnahme: Mit der HVB Mastercard / HVB Mastercard Gold
im HVB AktivKonto und HVB PlusKonto 2,50 EUR
HVB Reisestellenkarte: nicht möglich"""

REVOLUT_ATM = """\
## Virtuelle Revolut-Karten

- Kostenlos.

## Ausgaben

Der folgende Abschnitt gilt ab dem 15. Oktober 2026

## Bargeldabhebungen am Geldautomaten

- Bis zu 5 Abhebungen am Geldautomaten oder 200 € (je nachdem, was zuerst eintritt) pro rollierendem Monat sind gebührenfrei. Weitere Abhebungen werden mit 2 % des Abhebungsbetrags oder 1 € berechnet, je nachdem, welcher Betrag höher ist.
- Kartenlose Geldautomatenauszahlungen mit BLIK: Für jede Auszahlung berechnen wir eine Gebühr von 2 % des abgehobenen Betrags bzw. mindestens 5 PLN (je nachdem, welcher Betrag höher ist). Diese Gebühr buchen wir immer von deinem PLN-Unterkonto ab. Für alle anderen Geldautomatenauszahlungen gelten die oben aufgeführten Gebühren (falls zutreffend)."""  # noqa: E501


def _dev_golden_holdout():
    return set(json.loads((ROOT / "evals/golden_real.json").read_text())["holdout"])


def _dev_golden_rules():
    golden = json.loads((ROOT / "evals/golden_real.json").read_text())
    holdout = _dev_golden_holdout()  # filtered out before any rule content is touched
    dev = {label: rules for label, rules in golden["rules"].items() if label.partition(":")[0] not in holdout}
    return [(label, r) for label, rules in dev.items() for r in rules]


DEV_GOLDEN_RULES = _dev_golden_rules()


def test_c24_allowance_row_and_next_price_row_are_one_section():
    lay = layout([C24_PAGE3])
    [s] = [s for s in lay.sections if any("4 x 0,00 EUR" in line for line in s.lines)]
    assert any("Jede weitere Bargeldauszahlung mit der C24 Mastercard" in line for line in s.lines)
    assert lay.headings[s.headings[-1]].startswith("1. Bargeldauszahlungen am Geldautomaten")
    assert lay.tables[s.table][1:] == ["C24 Smartkonto", "C24 Pluskonto", "C24 Maxkonto", "C24 Basiskonto"]


def test_hvb_wrapped_prose_keeps_the_exception_lines():
    [s] = [s for s in layout([HVB_ATM]).sections if any("2% mind. 5 EUR" in line for line in s.lines)]
    assert any("Ausnahme: Mit der HVB Mastercard" in line for line in s.lines)


def test_revolut_bullet_under_markdown_heading():
    lay = layout([REVOLUT_ATM])
    [s] = [s for s in lay.sections if any("Bis zu 5 Abhebungen" in line for line in s.lines)]
    assert lay.headings[s.headings[-1]] == "## Bargeldabhebungen am Geldautomaten"


def test_page_without_headings_is_one_section_with_empty_path():
    [s] = layout(["Bargeld weltweit | 0,- €\nSollzins 22,60 %"]).sections
    assert (s.headings, s.page, s.start) == ([], 1, 0)


def test_repeated_table_header_on_the_next_page_is_a_new_table():
    header = "| | A | B |\n|---|---|---|\n"
    lay = layout([header + "| Gebühr | 1,00 EUR | 2,00 EUR |", header + "| Entgelt | 3,00 EUR | 4,00 EUR |"])
    assert [s.table for s in lay.sections] == [0, 1]
    assert lay.tables == [["", "A", "B"], ["", "A", "B"]]


def test_long_price_run_is_split_under_max_lines():
    page = "\n".join(f"Posten {i} | {i},00 EUR" for i in range(10))
    sections = layout([page], max_lines=4).sections
    assert [len(s.lines) for s in sections] == [4, 4, 2]
    assert [s.start for s in sections] == [0, 4, 8]


def test_split_keeps_lead_in_lines_and_skips_leading_blanks():
    page = "Kopf | 1,00 EUR\nLeadin ohne Preis\n\nPosten 2,00 EUR\nPosten 3,00 EUR"
    sections = layout([page], max_lines=3).sections
    assert any("Leadin ohne Preis" in s.lines for s in sections)
    assert all(s.lines[0].strip() for s in sections)


def test_header_row_with_a_price_is_section_content():
    lay = layout(["| Kartenentgelt | 4,90 € pro Monat |\n|---|---|\n| Sollzins | 22,60 % |"])
    [s] = lay.sections
    assert s.lines == ["| Kartenentgelt | 4,90 € pro Monat |", "|---|---|", "| Sollzins | 22,60 % |"]
    assert lay.tables == [["Kartenentgelt", "4,90 € pro Monat"]] and s.table == 0


def test_markdown_line_with_a_price_is_content_not_heading():
    lay = layout(["## Entgelte\n## kostenfrei\nPosten 2,00 EUR"])
    assert lay.headings == ["## Entgelte"]
    [s] = lay.sections
    assert s.lines == ["## kostenfrei", "Posten 2,00 EUR"]


DEV_DOCS = sorted(
    p.stem for p in (ROOT / "catalog/docs").glob("*.pdf") if p.stem.split("_")[0] not in _dev_golden_holdout()
)


@pytest.mark.parametrize("doc", DEV_DOCS)
def test_every_price_line_of_a_dev_document_is_in_a_section(doc):
    pages = read_text(ROOT / f"catalog/docs/{doc}.pdf")
    covered = {(s.page, s.start + k) for s in layout(pages).sections for k in range(len(s.lines))}
    lost = [
        (n, i, line)
        for n, page in enumerate(pages, 1)
        for i, line in enumerate(page.splitlines())
        if PRICE.search(line) and not line.strip().startswith("<!--") and (n, i) not in covered
    ]
    assert lost == []


def test_lines_are_verbatim_and_sections_stay_on_their_page():
    pages = [C24_PAGE3, HVB_ATM]
    for s in layout(pages).sections:
        assert pages[s.page - 1].splitlines()[s.start : s.start + len(s.lines)] == s.lines
        assert len(s.lines) <= MAX_LINES


@pytest.mark.parametrize("label,rule", DEV_GOLDEN_RULES, ids=lambda v: v if isinstance(v, str) else v["id"])
def test_every_dev_golden_quote_is_inside_one_section(label, rule):
    pages = read_text(ROOT / f"catalog/docs/{label.partition(':')[0]}.pdf")
    texts = [_squash("\n".join(s.lines)) for s in layout(pages).sections if s.page == rule["page"]]
    assert any(_squash(rule["quote"]) in t for t in texts), rule["id"]


def test_c24_columns_group_by_identical_cells():
    lay = layout([C24_PAGE3])
    s = next(s for s in lay.sections if any("4 x 0,00 EUR" in x for x in s.lines))
    assert sorted(v.columns for v in views(s, lay)) == [
        ["C24 Basiskonto"],
        ["C24 Pluskonto", "C24 Maxkonto"],
        ["C24 Smartkonto"],
    ]


def test_tags_resolve_to_numbers_on_their_line_and_words_are_not_tagged():
    s = Section("p1.0", 1, 0, ["Mit der C24 Mastercard | 4 x 0,00 EUR 7", "Jede weitere | 2,00 EUR"], [], None)
    [v] = views(s, Layout([], [], [s]))
    assert "C24" in v.text and "C[n" not in v.text
    assert v.numbers == {"n1": Decimal(4), "n2": Decimal("0.00"), "n3": Decimal(7), "n4": Decimal("2.00")}
    assert v.tag_line["n4"] == 1 and "[n4]2,00" in v.text


def test_single_column_group_has_no_columns():
    lay = layout([CONSORS_DEBIT_TABLE])
    vs = [v for s in lay.sections for v in views(s, lay)]
    assert vs and all(v.columns == [] for v in vs)
    assert all("|---" not in v.text for v in vs)


def test_column_of_only_dashes_gives_no_view():
    lines = ["| Cash | 2,00 EUR | - |", "| Card | 3,00 EUR | - |"]
    s = Section("p1.0", 1, 0, lines, [], 0)
    lay = Layout([], [["t", "A", "B"]], [s])
    [v] = views(s, lay)
    assert v.columns == [] and "2,00" in v.text
