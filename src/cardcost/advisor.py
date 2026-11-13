import logging
import re
from difflib import SequenceMatcher

from cardcost import db
from cardcost.calc import rank
from cardcost.fees import read_fees
from cardcost.models import CostLine, FeeSchedule, Scenario, Usage
from cardcost.numbers import parse_german_decimal

log = logging.getLogger("cardcost.advisor")


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def match_product(wanted: str, options: list[FeeSchedule]) -> list[FeeSchedule]:
    """Exact name first; else the products containing every word of `wanted` with the fewest extra words.
    One result is a match; several are equally good, so the user chooses. Punctuation is ignored, so
    "HVB Mastercard / HVB AktivKonto" finds "HVB Mastercard (HVB AktivKonto)"."""
    named = [f for f in options if f.product]
    exact = [f for f in named if f.product.lower() == wanted.lower()]
    if len(exact) == 1:
        return exact
    want = _words(wanted)
    extra = {id(f): len(_words(f.product) - want) for f in named if want <= _words(f.product)}
    return [f for f in named if extra and extra.get(id(f)) == min(extra.values())]


COMPARE = re.compile(r"welche karte|günstigste|vergleich|which card|cheapest", re.IGNORECASE)
_GENERIC = {"preis", "leistung", "card", "karte"}


def _named(token: str, seen: set[str]) -> bool:
    # shortcut: cards are named by their file name; long names match fuzzily ("Trade Republic" ~ traderepublik),
    # short ids (ing, dkb) only exactly. Upgrade to a name list per card when a bank's name and file name differ more.
    if len(token) <= 4:
        return token in seen
    return any(SequenceMatcher(None, token, w).ratio() >= 0.85 for w in seen)


def mentioned(question: str, wallet: list[str]) -> list[str]:
    """Wallet entries the question names. Of a named card, the entries whose product words all appear win,
    the most specific first ("HVB AktivKonto … Mastercard" -> the AktivKonto entry); otherwise all its entries."""
    words = re.findall(r"\w+", question.lower())
    seen = set(words) | {a + b for a, b in zip(words, words[1:], strict=False)}
    found = []
    for card in dict.fromkeys(e.partition(":")[0] for e in wallet):
        if not any(_named(t, seen) for t in set(re.split(r"[-_]", card.lower())) - _GENERIC):
            continue
        entries = [e for e in wallet if e.partition(":")[0] == card]
        size = {e: len(_words(e.partition(":")[2])) for e in entries if _words(e.partition(":")[2]) <= seen}
        size = {e: n for e, n in size.items() if n}
        found += [e for e in entries if size and size.get(e) == max(size.values())] or entries
    return found


class Advisor:
    def __init__(self, fees: dict[str, list[FeeSchedule]], llm=None, wallet: list[str] | None = None):
        self.by_card, self.llm = fees, llm
        self.wallet = wallet or sorted(fees)
        self.fees: dict[str, FeeSchedule | None] = {}
        self.choices: dict[str, list[FeeSchedule]] = {}  # wallet entry -> products the user must choose between

    def scope(self, question: str) -> list[str]:
        """A question naming cards is about those cards only; a comparison ("welche Karte …") covers the wallet."""
        if COMPARE.search(question):
            return self.wallet
        return mentioned(question, self.wallet) or self.wallet

    def resolve(self, question: str, wallet: list[str] | None = None) -> dict[str, FeeSchedule | None]:
        """Wallet entry 'card' or 'card:Product' -> its fees. A multi-product card without a choice lists all.
        Only the cards the question is about (see scope); `wallet` overrides that for this call."""
        fees: dict[str, FeeSchedule | None] = {}
        self.choices = {}
        for entry in wallet or self.scope(question):
            card, _, product = entry.partition(":")
            options = self.by_card.get(card, [])
            if product:
                found = match_product(product, options)
                fees[entry] = found[0] if len(found) == 1 else None
                if fees[entry] is None:  # never guess: a tie, or with no match every product, goes back to the user
                    self.choices[entry] = found or [f for f in options if f.product]
                    log.warning("product_not_resolved", extra={"entry": entry, "found": [f.product for f in options]})
            elif len(options) <= 1:
                fees[entry] = options[0] if options else None
            else:
                fees |= {f"{card}:{f.product}": f for f in options}
        self.fees = fees
        return fees

    def choice_labels(self) -> dict[str, list[str]]:
        """Unresolved wallet entry -> the 'card:Product' entries the user can choose from."""
        return {e: [f"{e.partition(':')[0]}:{f.product}" for f in fs] for e, fs in self.choices.items()}

    def cost_table(self, question: str, scenario: Scenario, wallet: list[str] | None = None) -> list[CostLine]:
        return rank(self.resolve(question, wallet), scenario)


COUNTRIES = {
    "deutschland": "DE",
    "inland": "DE",
    "frankreich": "FR",
    "österreich": "AT",
    "italien": "IT",
    "spanien": "ES",
    "niederlande": "NL",
    "usa": "US",
    "vereinigten staaten": "US",
    "amerika": "US",
    "schweiz": "CH",
    "großbritannien": "GB",
    "england": "GB",
    "türkei": "TR",
    "polen": "PL",
    "japan": "JP",
    "thailand": "TH",
}
_AMOUNT = re.compile(r"(\d[\d.,]*)\s*(?:EUR|€|Euro)", re.IGNORECASE)
_PURCHASE = re.compile(r"bezahl|zahlung|einkauf|kauf|umsatz|shopping", re.IGNORECASE)


def parse_scenario(question: str, **overrides) -> Scenario:
    """Deterministic: amount from 'N EUR', country from a name list, purchase vs cash from keywords."""
    fields: dict = {"kind": "purchase" if _PURCHASE.search(question) else "cash", "country": "DE"}
    if m := _AMOUNT.search(question):
        fields["amount_eur"] = parse_german_decimal(m.group(1))
    lowered = question.lower()
    for name, code in COUNTRIES.items():
        if name in lowered:
            fields["country"] = code
            break
    fields |= {k: v for k, v in overrides.items() if v is not None}
    if "amount_eur" not in fields:
        raise ValueError("no amount found; write e.g. '300 EUR' or pass --amount")
    return Scenario(**fields)


def parse_usage(items: list[str]) -> dict[str, Usage]:
    """['c24=2', 'revolut=3:150:400'] -> withdrawals, EUR withdrawn and EUR exchanged so far this allowance period."""
    used = {}
    for item in items:
        label, sep, value = item.partition("=")
        if not sep:
            raise ValueError(f"usage must look like card=N[:EUR[:FX_EUR]], got {item!r}")
        count, amount, fx = (value.split(":") + ["", ""])[:3]
        used[label.strip()] = Usage(
            count=int(count),
            eur=parse_german_decimal(amount) if amount else None,
            fx_eur=parse_german_decimal(fx) if fx else None,
        )
    return used


def build_advisor(conn, live: bool = True) -> Advisor:
    from cardcost.llm import LLM

    return Advisor(read_fees(), LLM(conn=conn, live=live), wallet=db.wallet(conn))
