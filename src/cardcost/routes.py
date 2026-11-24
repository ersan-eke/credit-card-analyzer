"""Keyword router: which event questions a section view must be asked."""

import re
import unicodedata
from typing import NamedTuple

from cardcost.sections import PRICE, Layout, View

ROUTES = ("cash", "payment", "credit", "holding")
ROUTE_EVENTS: dict[str, set[str]] = {
    "cash": {"atm", "counter_cash"},
    "payment": {"payment", "atm"},
    "credit": {"credit"},
    "holding": {"holding"},
}
_KEYWORDS = {
    "cash": r"bargeld(?!los)|geldautomat|abhebung|auszahlung|schalter|atm|cash|withdraw",
    "payment": r"fremdwähr|währung|auslandseinsatz|euroraum|au(?:ß|ss)erhalb der eu"
    r"|currency|exchange|wochenende|weekend|casino|lotterie|wett|gambling",
    "credit": r"sollzins|zinss|teilzahl|interest",
    "holding": r"jahresgebühr|jahrespreis|kartenpreis|kartengebühr|grundpreis|monatlich|pro monat"
    r"|plan fee|subscription",
}
_PATTERNS = {r: re.compile(_KEYWORDS[r]) for r in ROUTES}


class Routing(NamedTuple):
    routes: list[str]  # keyword routes, in ROUTES order
    triage: bool  # some price line no keyword explains
    example: bool  # a heading in the path contains "Beispiel": no call


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold()


def _matches(text: str) -> set[str]:
    return {r for r, p in _PATTERNS.items() if p.search(text)}


def route(view: View, lay: Layout) -> Routing:
    headings = [_norm(lay.headings[i]) for i in view.section.headings]
    lines = [_norm(x) for x in view.text.split("\n")]
    found = _matches("\n".join([*lines, *headings]))
    last = _matches(headings[-1]) if headings else set()
    triage, segment = False, []
    for line in lines:
        segment.append(line)
        if PRICE.search(line):  # lines after the previous price line, up to this one
            triage |= not (_matches("\n".join(segment)) | last)
            segment = []
    return Routing([r for r in ROUTES if r in found], triage, any("beispiel" in h for h in headings))
