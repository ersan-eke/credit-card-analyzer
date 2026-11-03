import logging
import os
import re
from pathlib import Path

from cardcost import db
from cardcost.calc import rank
from cardcost.extract import extract_fees
from cardcost.models import CostLine, FeeSchedule, Passage, Scenario, Usage
from cardcost.numbers import parse_german_decimal
from cardcost.retrieval import Retriever

log = logging.getLogger("cardcost.advisor")
# Always retrieved next to the user's question, so a vague question cannot starve extraction of the fee pages.
FEE_QUERY = (
    "Bargeldauszahlung Geldautomat Entgelt Fremdwährung Auslandseinsatzentgelt Sollzinssatz Bargeldverfügung "
    "Geldautomatenbetreiber Gebühr"
)


class Advisor:
    def __init__(self, retriever: Retriever, llm, wallet: list[str] | None = None, conn=None, k: int = 3):
        self.retriever, self.llm, self.k = retriever, llm, k
        self.conn = conn if conn is not None else db.connect(":memory:")
        self.wallet = wallet or sorted({p.card_id for p in retriever.passages})
        self.fees: dict[str, FeeSchedule | None] = {}

    def passages_for(self, card_id: str, question: str) -> list[Passage]:
        found = self.retriever.search(question, card_id, self.k) + self.retriever.search(FEE_QUERY, card_id, self.k)
        unique = {p.id: p for p in found}
        return sorted(unique.values(), key=lambda p: p.id)

    def resolve(self, question: str) -> dict[str, FeeSchedule | None]:
        """Wallet entry 'card' or 'card:Product' -> its fees. A multi-product card without a choice lists all."""
        by_card: dict[str, list[FeeSchedule]] = {}
        fees: dict[str, FeeSchedule | None] = {}
        for entry in self.wallet:
            card, _, product = entry.partition(":")
            if card not in by_card:
                by_card[card] = extract_fees(card, self.passages_for(card, question), self.llm, self.conn)
            options = by_card[card]
            if product:
                exact = [f for f in options if f.product and product.lower() == f.product.lower()]
                match = exact or [f for f in options if f.product and product.lower() in f.product.lower()]
                fees[entry] = match[0] if len(match) == 1 else None
                if len(match) != 1:
                    log.warning("product_not_found", extra={"entry": entry, "found": [f.product for f in options]})
            elif len(options) <= 1:
                fees[entry] = options[0] if options else None
            else:
                fees |= {f"{card}:{f.product}": f for f in options}
        self.fees = fees
        return fees

    def cost_table(self, question: str, scenario: Scenario) -> list[CostLine]:
        return rank(self.resolve(question), scenario)


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
    """['c24=2', 'revolut=3:150'] -> withdrawals (and EUR) already used in the current free-allowance period."""
    used = {}
    for item in items:
        label, sep, value = item.partition("=")
        if not sep:
            raise ValueError(f"usage must look like card=N or card=N:EUR, got {item!r}")
        count, _, amount = value.partition(":")
        used[label.strip()] = Usage(count=int(count), eur=parse_german_decimal(amount) if amount else None)
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
