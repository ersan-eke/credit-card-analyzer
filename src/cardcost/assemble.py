"""An answered fee becomes validated rules by code: numbers from tags, quote and page from the section."""

import logging
import re
from decimal import Decimal
from typing import Literal, NamedTuple

from pydantic import ValidationError

from cardcost.models import Allowance, Amount, Price, Rule, When
from cardcost.sections import View

log = logging.getLogger("cardcost.assemble")

CONDITION_KINDS = ("account_model", "plan", "status")
_SUFFIX = re.compile(r"\s*[\[(][^\])]*[\])]\s*$|\s+\d+[A-Za-z]?$")


class Condition(NamedTuple):
    name: str  # as printed
    kind: Literal["account_model", "plan", "status"]


class Document(NamedTuple):
    cards: list[str]  # cleaned product names
    conditions: list[Condition]
    document_for: int | None  # 0-based index into conditions
    fee_headings: set[int]  # Layout.headings ids about card fees
    table_columns: dict[int, str]  # Layout.tables id -> "cards" | "account_model" | "plan" | "status" | "none"


def clean_product(name: str) -> str:
    return _SUFFIX.sub("", name).strip()


def build_rules(fee: dict, view: View, doc: Document) -> list[tuple[str | None, Rule]]:
    label = f"fee {fee.get('name')!r}"
    used: list[str] = []

    def tag(key: str, whole: bool = False) -> Decimal | None:
        t = fee.get(key) or ""
        if not t:
            return None
        if t not in view.numbers:
            raise ValueError(f"{label}: unknown tag {t!r} in {key}")
        v = view.numbers[t]
        if whole and (v.as_tuple().exponent < 0 or v <= 0):
            raise ValueError(f"{label}: {key} {t} is not a whole number")
        used.append(t)
        return v

    def pick(key: str, items: list) -> list:
        idx = fee.get(key) or []
        if not all(1 <= i <= len(items) for i in idx):
            raise ValueError(f"{label}: {key} {idx} out of range 1..{len(items)}")
        return [items[i - 1] for i in idx]

    try:
        price_nums = {k: tag(k) for k in ("percent", "flat_eur", "min_eur", "max_eur")}
        if any(v is not None for v in price_nums.values()):
            price = Price(**price_nums)
        else:
            price = Price(flat_eur=Decimal(0)) if fee.get("free") else None
        count, amount = tag("allowance_count", whole=True), tag("allowance_amount")
        period = fee.get("allowance_period") or "none"
        if period == "none" and (count is not None or amount is not None):
            raise ValueError(f"{label}: allowance without a period")
        allowance = (
            None
            if period == "none"
            else Allowance(count=int(count) if count is not None else None, amount_eur=amount, period=period)
        )
        lo, hi = tag("amount_min"), tag("amount_max")
        days = tag("interest_free_days", whole=True)
        facts: dict[str, list[str]] = {}
        for c in pick("only_for", doc.conditions):
            facts.setdefault(c.kind, []).append(c.name)
        if doc.document_for is not None:
            own = doc.conditions[doc.document_for]
            if own.kind in facts:
                if own.name in facts[own.kind]:
                    del facts[own.kind]
                else:
                    log.info("plan_dropped: %s is for %s, the document is for %s", label, facts[own.kind], own.name)
                    return []
        kind = doc.table_columns.get(view.section.table) if view.section.table is not None else None
        if view.columns and kind in CONDITION_KINDS:
            facts[kind] = view.columns
        if len(doc.cards) <= 1:
            products: list[str | None] = [None]
        elif view.columns and kind == "cards":
            products = [clean_product(c) for c in view.columns]
        else:
            products = pick("cards", doc.cards) or list(doc.cards)
        lines = view.section.lines
        if used:
            idx = [view.tag_line[t] for t in used]
            lines = lines[min(idx) : max(idx) + 1]
        rule = Rule(
            name=fee["name"],
            event=fee["event"],
            when=When(amount=Amount(min=lo, max=hi) if lo is not None or hi is not None else None, facts=facts or None),
            price=price,
            allowance=allowance,
            per=None if fee.get("per") in (None, "none") else fee["per"],
            waiver=fee.get("waiver") or None,
            interest_free_days=int(days) if days is not None else None,
            quote="\n".join(lines),
            page=view.section.page,
        )
    except ValidationError as e:
        raise ValueError(f"{label}: {e}") from e
    return [(p, rule) for p in products]


def merge_rules(rules: list[tuple[str | None, Rule]]) -> dict[str | None, list[Rule]]:
    out: dict[str | None, list[Rule]] = {}
    skip = {"name", "quote", "page"}
    for product, r in rules:
        kept = out.setdefault(product, [])
        if not any(r.model_dump(exclude=skip) == k.model_dump(exclude=skip) for k in kept):
            kept.append(r)
    return out
