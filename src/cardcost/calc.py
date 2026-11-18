"""All money maths. Decimal only, no floats, no LLM. Each component is rounded half-up to cents, then summed."""

from datetime import UTC, datetime
from decimal import Decimal

from cardcost.models import CostLine, FeeSchedule, Rule, Scenario, Usage
from cardcost.numbers import to_cents

ZERO = Decimal(0)


def cash_cost(fee: FeeSchedule, amount: Decimal) -> Decimal:
    return to_cents(max(amount * (fee.percent or ZERO) / 100, fee.min_eur or ZERO))


def cash_base(fee: FeeSchedule, amount: Decimal, used: Usage | None) -> tuple[Decimal, str | None]:
    """Amount the cash fee applies to after the card's allowance. Unknown usage counts as used up: never assume free.
    A withdrawal that only partly fits a free amount is charged on the part above the limit."""
    if fee.free_from_eur is not None and amount >= fee.free_from_eur:
        return ZERO, f"kostenlos ab {fee.free_from_eur} EUR"
    if fee.free_count is None and fee.free_amount_eur is None:
        return amount, None
    if used is None or (fee.free_amount_eur is not None and used.eur is None):
        return amount, "Freikontingent als verbraucht angenommen (bisherige Abhebungen nicht angegeben)"
    if fee.free_count is not None and used.count >= fee.free_count:
        base = amount
    elif fee.free_amount_eur is None:
        base = ZERO
    else:
        base = max(ZERO, amount - max(ZERO, fee.free_amount_eur - used.eur))
    limits = []
    if fee.free_count is not None:
        limits.append(f"{fee.free_count} Abhebungen")
    if fee.free_amount_eur is not None:
        limits.append(f"{fee.free_amount_eur} EUR")
    so_far = f"{used.count} Abhebungen" + (f" / {used.eur} EUR" if used.eur is not None else "")
    state = "kostenlos" if base == ZERO else "verbraucht" if base == amount else f"berechnet auf {base} EUR"
    return base, f"Freikontingent {' / '.join(limits)}, bisher {so_far}: {state}"


def fx_base(fee: FeeSchedule, amount: Decimal, used: Usage | None) -> tuple[Decimal, str | None]:
    """Amount the FX fee applies to. With an exchange allowance only the excess is charged ("für den zusätzlichen
    Betrag"); unknown usage counts as used up."""
    if fee.fx_free_eur is None:
        return amount, None
    if used is None or used.fx_eur is None:
        return amount, "Wechsellimit als verbraucht angenommen (bisheriger Umtausch nicht angegeben)"
    left = max(ZERO, fee.fx_free_eur - used.fx_eur)
    return max(ZERO, amount - left), f"Wechsellimit {fee.fx_free_eur} EUR, bisher {used.fx_eur} EUR umgetauscht"


def rule_matches(rule: Rule, event: str, s: Scenario) -> bool:
    w = rule.when
    return (
        event in rule.event
        and (w.currency is None or s.currency in w.currency)
        and (w.region is None or s.region in w.region)
        and (w.country is None or s.country.upper() in w.country)
        and (w.amount is None or w.amount.min is None or s.amount_eur >= w.amount.min)
        and (w.amount is None or w.amount.max is None or s.amount_eur < w.amount.max)
        and (w.network is None or s.atm_network in w.network)
        and (w.merchant is None or s.merchant in w.merchant)
        and (w.weekend is None or w.weekend.contains(s.at or datetime.now(UTC)))
    )


def rule_base(rule: Rule, amount: Decimal, used: Usage | None) -> tuple[Decimal, str | None]:
    """Amount a rule's price applies to after its allowance. Unknown usage counts as used up: never assume free.
    A use that only partly fits a free amount is charged on the part above the limit. An allowance on a foreign-currency
    rule counts EUR exchanged (fx_eur), any other counts EUR withdrawn (eur)."""
    a = rule.allowance
    if a is None:
        return amount, None
    spent = None if used is None else used.fx_eur if rule.is_fx else used.eur
    if used is None or (a.amount_eur is not None and spent is None):
        return amount, f"Freikontingent {rule.name} als verbraucht angenommen (bisherige Nutzung nicht angegeben)"
    if a.count is not None and used.count >= a.count:
        base = amount
    elif a.amount_eur is None:
        base = ZERO
    else:
        base = max(ZERO, amount - max(ZERO, a.amount_eur - spent))
    limits = " / ".join(
        [*([f"{a.count} Nutzungen"] if a.count is not None else []), *([f"{a.amount_eur} EUR"] if a.amount_eur else [])]
    )
    state = "kostenlos" if base == ZERO else "verbraucht" if base == amount else f"berechnet auf {base} EUR"
    so_far = f"{used.count}" + (f" / {spent} EUR" if spent is not None else "")
    return base, f"Freikontingent {rule.name} {limits} ({a.period}), bisher {so_far}: {state}"


def rule_fee(rule: Rule, base: Decimal) -> Decimal:
    p = rule.price
    if not base:
        return ZERO
    fee = base * (p.percent or ZERO) / 100 + (p.flat_eur or ZERO)
    fee = max(fee, p.min_eur or ZERO)
    return to_cents(min(fee, p.max_eur) if p.max_eur is not None else fee)


def applicable(fee: FeeSchedule, event: str, s: Scenario) -> tuple[Rule | None, list[Rule]]:
    """The base rule (most specific of those that match; a tie is an error) and the rules that stack on it."""
    hits = [r for r in fee.rules if rule_matches(r, event, s)]
    base = [r for r in hits if not r.stacks]
    top = max((r.when.specificity for r in base), default=0)
    best = [r for r in base if r.when.specificity == top]
    if len(best) > 1:
        raise ValueError(f"{fee.card} {fee.product or ''}: rules tie for {event}: {', '.join(r.name for r in best)}")
    return (best[0] if best else None), [r for r in hits if r.stacks]


REPAYMENT = ("pays_in_full", "instalments")
PER = {"month": "Monat", "year": "Jahr"}


def with_user_value(rule: Rule, label: str, s: Scenario) -> tuple[Rule, bool]:
    """A rule the document leaves unpriced takes the user's own price, if they gave one."""
    own = s.provided_for(label, rule.name) if rule.price is None else None
    return (rule.model_copy(update={"price": own}), True) if own else (rule, False)


def holding_text(rule: Rule, own: bool) -> str:
    """A recurring fee as shown beside the cost. A waiver (often tied to spend) is worded, never credited."""
    p = rule.price
    price = " + ".join(
        [
            *([f"{p.flat_eur} EUR"] if p and p.flat_eur is not None else []),
            *([f"{p.percent} %"] if p and p.percent else []),
        ]
    )
    per = f" pro {PER[rule.per]}" if rule.per else ""
    return (
        (f"{rule.name} {price}{per}" if price else f"{rule.name} nicht angegeben")
        + (f" (entfällt: {rule.waiver})" if rule.waiver else "")
        + (" (Wert vom Nutzer)" if own else "")
    )


def rules_cost_line(label: str, fee: FeeSchedule, s: Scenario) -> CostLine:
    comps: dict[str, Decimal] = {}
    missing: list[str] = []
    notes: list[str] = []
    used: list[Rule] = []
    given: list[str] = []
    cash = s.kind == "cash"
    borrows = bool(s.days) and (cash or any("credit" in r.event for r in fee.rules))
    for event in ["atm" if cash else "payment"] + (["credit"] if borrows else []):
        if event == "credit" and not cash and s.facts.get("repayment_mode") not in REPAYMENT:
            missing.append(
                "repayment_mode"
            )  # a purchase is interest-free or not by how it is repaid: ask, never assume
            continue
        base, stacked = applicable(fee, event, s)
        if base is None and event != "payment":  # a payment is free of base fees unless the list says otherwise
            missing.append("cash_interest" if event == "credit" else "cash_fee")
        for rule in [*([base] if base else []), *stacked]:
            rule, own = with_user_value(rule, label, s)
            used.append(rule)
            if own:
                given.append(rule.name)
                notes.append(f"{rule.name}: Wert vom Nutzer, nicht aus dem Preisverzeichnis")
            if rule.price is None:
                missing.append(rule.name)
                continue
            if event == "credit":
                free = rule.interest_free_days
                if not cash and s.facts["repayment_mode"] == "pays_in_full" and (free is None or s.days <= free):
                    comps[rule.name] = ZERO  # cash is excluded from the interest-free period: it accrues from day one
                    notes.append(
                        "Zinsfrei bei vollständiger Rückzahlung" + (f" innerhalb {free} Tagen" if free else "")
                    )
                    continue
                interest = to_cents(s.amount_eur * (rule.price.percent or ZERO) / 100 * s.days / 365)
                comps[rule.name] = comps.get(rule.name, ZERO) + interest
                continue
            exchanged = max(ZERO, s.amount_eur - s.held_eur) if rule.is_fx else s.amount_eur
            amount, note = rule_base(rule, exchanged, s.usage_for(label))
            comps[rule.name] = comps.get(rule.name, ZERO) + rule_fee(rule, amount)
            notes += [note] if note else []
    holding = []
    for rule in fee.rules:
        if rule_matches(rule, "holding", s):
            rule, own = with_user_value(rule, label, s)
            holding.append(holding_text(rule, own))
            given += [rule.name] if own else []
    if s.kind == "cash" and s.operator_fee:
        if fee.network in s.operator_fee:
            comps["atm_operator_fee"] = to_cents(s.operator_fee[fee.network])
        else:
            missing.append("atm_operator_fee")  # which network's fee applies is not known: never assume free
    if s.currency != "EUR" and not any(r.is_fx for r in used):
        missing.append("fx_fee")
    pages = sorted({r.page for r in used} or {fee.source_page})
    return CostLine(
        label=label,
        components=comps,
        missing=missing,
        total=None if missing else sum(comps.values(), ZERO),
        source=f"{fee.source_file} p.{', '.join(map(str, pages))}",
        quote="\n".join(dict.fromkeys(r.quote for r in used)) or fee.quote,
        notes=notes,
        holding=holding,
        provided=given,
    )


def cost_line(label: str, fee: FeeSchedule | None, s: Scenario) -> CostLine:
    if fee is None:
        return CostLine(label=label, missing=["fee document"])
    if fee.rules:
        return rules_cost_line(label, fee, s)
    comps: dict[str, Decimal] = {}
    missing: list[str] = []
    notes: list[str] = []
    if s.kind == "cash":
        if fee.percent is None and fee.min_eur is None:
            missing.append("cash_fee")
        else:
            base, note = cash_base(fee, s.amount_eur, s.usage_for(label))
            comps["cash_fee"] = cash_cost(fee, base) if base else ZERO
            notes += [note] if note else []
        if s.abroad and fee.atm_operator_fee_eur is not None:
            comps["atm_operator_fee"] = to_cents(fee.atm_operator_fee_eur)
        if s.days:
            if fee.cash_interest_pa is None:
                missing.append("cash_interest")
            else:
                comps["interest"] = to_cents(s.amount_eur * fee.cash_interest_pa / 100 * s.days / 365)
    if s.foreign_currency:
        if fee.fx_percent is None:
            missing.append("fx_fee")
        else:
            base, note = fx_base(fee, s.amount_eur, s.usage_for(label))
            comps["fx_fee"] = to_cents(base * fee.fx_percent / 100)
            notes += [note] if note else []
    return CostLine(
        label=label,
        components=comps,
        missing=missing,
        total=None if missing else sum(comps.values(), ZERO),
        source=f"{fee.source_file} p.{fee.source_page}",
        quote=fee.quote,
        notes=notes,
    )


def rank(fees: dict[str, FeeSchedule | None], s: Scenario) -> list[CostLine]:
    """Cheapest first; cards with an unknown cost go last (never treated as free); ties by label."""
    lines = [cost_line(label, fee, s) for label, fee in fees.items()]
    return sorted(lines, key=lambda ln: (ln.total is None, ln.total or ZERO, ln.label))


def matrix(
    fees: dict[str, FeeSchedule | None], kind: str, country: str, max_amount: int = 2000, used: dict | None = None
):
    """Winner bands [(from_eur, to_eur, label)] for the next transaction, given allowance usage so far."""
    # shortcut: 1-EUR scan instead of solving the piecewise-linear crossovers; exact enough for advice up to ~10k EUR
    bands: list[tuple[int, int, str]] = []
    for amount in range(1, max_amount + 1):
        best = rank(fees, Scenario(kind=kind, amount_eur=Decimal(amount), country=country, used=used or {}))[0]
        winner = best.label if best.total is not None else "unknown"
        if bands and bands[-1][2] == winner:
            bands[-1] = (bands[-1][0], amount, winner)
        else:
            bands.append((amount, amount, winner))
    return bands
