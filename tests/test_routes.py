import unicodedata

import pytest
from test_sections import ROOT, _dev_golden_rules

from cardcost.extract import _squash
from cardcost.ingest import read_text
from cardcost.routes import ROUTE_EVENTS, Routing, route
from cardcost.sections import Layout, Section, layout, views


def _view(lines, headings=(), heading_ids=None):
    s = Section("p1.0", 1, 0, list(lines), list(heading_ids if heading_ids is not None else range(len(headings))), None)
    lay = Layout(list(headings), [], [s])
    return views(s, lay)[0], lay


def test_unknown_wording_next_to_a_keyword_line_goes_to_triage():
    r = route(*_view(["Kartenpreis monatlich | 2,00 €", "Geld aus der Wand | 1,50 €"]))
    assert r.routes == ["holding"] and r.triage and not r.example


def test_label_on_an_earlier_line_explains_the_price():
    r = route(*_view(["Sollzins p.a.", "", "22,60 % (veränderlich*)"]))
    assert r.routes == ["credit"] and not r.triage


def test_last_heading_explains_bare_rows():
    r = route(*_view(["Jede weitere | 2,00 EUR"], ["1. Bargeldauszahlungen am Geldautomaten"]))
    assert r.routes == ["cash"] and not r.triage


def test_bargeldlos_is_not_cash():
    r = route(*_view(["Bargeldloser Einsatz im Ausland | 1,50 %"]))
    assert "cash" not in r.routes


def test_nfd_and_upper_case_match():
    nfd = lambda s: unicodedata.normalize("NFD", s)  # noqa: E731
    lines = [nfd("FREMDWÄHRUNG | 1,75 %"), nfd("GELDAUTOMAT | 2,00 EUR")]
    assert lines[0] != "FREMDWÄHRUNG | 1,75 %"
    r = route(*_view(lines))
    assert r.routes == ["cash", "payment"] and not r.triage


def test_example_heading_flags_the_view():
    r = route(*_view(["Sollzins 22,60 %"], ["## Repräsentatives Beispiel nach § 5 VKrG"]))
    assert r.example


def test_no_price_line_and_no_keyword_needs_nothing():
    assert route(*_view(["Online abrufbar"])) == Routing([], False, False)


TRIAGE_ONLY: set[str] = set()  # golden rule ids reached only through triage; each one named, none stale


@pytest.mark.parametrize("label,rule", _dev_golden_rules(), ids=lambda x: x if isinstance(x, str) else x["id"])
def test_every_dev_golden_rule_is_routed_or_named_for_triage(label, rule):
    pages = read_text(ROOT / f"catalog/docs/{label.partition(':')[0]}.pdf")
    lay = layout(pages)
    quote = _squash(rule["quote"])
    found = [
        (v, route(v, lay))
        for s in lay.sections
        if s.page == rule["page"] and quote in _squash("\n".join(s.lines))
        for v in views(s, lay)
    ]
    routed = any(not r.example and any(ROUTE_EVENTS[x] >= set(rule["event"]) for x in r.routes) for _, r in found)
    if rule["id"] in TRIAGE_ONLY:
        assert not routed and any(r.triage for _, r in found)
    else:
        assert routed
