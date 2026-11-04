import logging
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

from cardcost import db
from cardcost.calc import rank
from cardcost.extract import extract_fees
from cardcost.models import CostLine, FeeSchedule, Passage, Scenario, Usage
from cardcost.numbers import parse_german_decimal
from cardcost.retrieval import Retriever

log = logging.getLogger("cardcost.advisor")
# Always retrieved next to the user's question, so a vague question cannot starve extraction of the fee pages.
# One line per fee, with every name the price lists use for it; a new synonym is a one-line change.
FEE_QUERY = " ".join(
    [
        "Bargeldauszahlung Bargeldverfügung Abhebung Geldautomat Entgelt Gebühr",
        "Fremdwährung Auslandseinsatzentgelt Währungsumrechnungsentgelt Wechselgebühr Wechsellimit",
        "Geldautomatenbetreiber Sollzinssatz",
    ]
)


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
    def __init__(self, retriever: Retriever, llm, wallet: list[str] | None = None, conn=None, k: int = 3):
        self.retriever, self.llm, self.k = retriever, llm, k
        self.conn = conn if conn is not None else db.connect(":memory:")
        self.wallet = wallet or sorted({p.card_id for p in retriever.passages})
        self.fees: dict[str, FeeSchedule | None] = {}
        self.choices: dict[str, list[FeeSchedule]] = {}  # wallet entry -> products the user must choose between
        self.pages: dict[str, int] = {}
        for p in retriever.passages:
            self.pages[p.card_id] = max(self.pages.get(p.card_id, 0), p.page)

    def k_for(self, card_id: str) -> int:
        # shortcut: one extra passage per 3 pages, so long price lists (HVB, Revolut) keep their fee pages in context;
        # measured on the real golden set: context recall 0.90 -> 0.95 (hybrid) for ~28 % more passages
        return max(self.k, self.pages.get(card_id, 0) // 3)

    def passages_for(self, card_id: str, question: str) -> list[Passage]:
        k = self.k_for(card_id)
        found = self.retriever.search(question, card_id, k) + self.retriever.search(FEE_QUERY, card_id, k)
        unique = {p.id: p for p in found}
        return sorted(unique.values(), key=lambda p: p.id)

    def scope(self, question: str) -> list[str]:
        """A question naming cards is about those cards only; a comparison ("welche Karte …") covers the wallet."""
        if COMPARE.search(question):
            return self.wallet
        return mentioned(question, self.wallet) or self.wallet

    def resolve(self, question: str, wallet: list[str] | None = None) -> dict[str, FeeSchedule | None]:
        """Wallet entry 'card' or 'card:Product' -> its fees. A multi-product card without a choice lists all.
        Only the cards the question is about (see scope); `wallet` overrides that for this call."""
        by_card: dict[str, list[FeeSchedule]] = {}
        fees: dict[str, FeeSchedule | None] = {}
        self.choices = {}
        for entry in wallet or self.scope(question):
            card, _, product = entry.partition(":")
            if card not in by_card:
                by_card[card] = extract_fees(card, self.passages_for(card, question), self.llm, self.conn)
            options = by_card[card]
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


def corpus_paths(conn) -> list[Path]:
    dirs = os.environ.get("CARDCOST_DOCS", "samples:data/private").split(":")
    paths = {p for d in dirs for p in Path(d).glob("*.pdf")}
    paths |= {Path(r["path"]) for r in conn.execute("SELECT path FROM ingest_job WHERE status = 'done'")}
    return sorted(p for p in paths if p.exists())


def build_advisor(conn, mode: str = "hybrid", live: bool = True) -> Advisor:
    from cardcost.ingest import ingest_paths
    from cardcost.llm import LLM
    from cardcost.retrieval import E5Embedder

    # shortcut: passages and embeddings are rebuilt per process (seconds for a few PDFs); persist if the corpus grows
    passages = ingest_paths(corpus_paths(conn))
    retriever = Retriever(passages, mode=mode, embedder=None if mode == "bm25" else E5Embedder())
    return Advisor(retriever, LLM(conn=conn, live=live), wallet=db.wallet(conn), conn=conn)
