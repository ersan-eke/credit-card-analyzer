import logging

from cardcost import db
from cardcost.calc import rank
from cardcost.extract import extract_fees
from cardcost.models import CostLine, FeeSchedule, Passage, Scenario
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
                match = [f for f in options if f.product and product.lower() in f.product.lower()]
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
