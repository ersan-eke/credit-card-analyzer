"""All money maths. Decimal only, no floats, no LLM. Each component is rounded half-up to cents, then summed."""

from decimal import Decimal

from cardcost.models import CostLine, FeeSchedule, Scenario, Usage
from cardcost.numbers import to_cents

ZERO = Decimal(0)


def cash_cost(fee: FeeSchedule, amount: Decimal) -> Decimal:
    return to_cents(max(amount * (fee.percent or ZERO) / 100, fee.min_eur or ZERO))


def allowance(fee: FeeSchedule, amount: Decimal, used: Usage | None) -> tuple[bool, str | None]:
    """Is this withdrawal free under the card's allowance? Unknown usage counts as used up: never assume free."""
    if fee.free_from_eur is not None and amount >= fee.free_from_eur:
        return True, f"kostenlos ab {fee.free_from_eur} EUR"
    if fee.free_count is None and fee.free_amount_eur is None:
        return False, None
    if used is None or (fee.free_amount_eur is not None and used.eur is None):
        return False, "Freikontingent als verbraucht angenommen (bisherige Abhebungen nicht angegeben)"
    # shortcut: a withdrawal that only partly fits the free amount is charged in full; no document here says otherwise
    free = (fee.free_count is None or used.count < fee.free_count) and (
        fee.free_amount_eur is None or used.eur + amount <= fee.free_amount_eur
    )
    limits = []
    if fee.free_count is not None:
        limits.append(f"{fee.free_count} Abhebungen")
    if fee.free_amount_eur is not None:
        limits.append(f"{fee.free_amount_eur} EUR")
    so_far = f"{used.count} Abhebungen" + (f" / {used.eur} EUR" if used.eur is not None else "")
    return free, f"Freikontingent {' / '.join(limits)}, bisher {so_far}: {'kostenlos' if free else 'verbraucht'}"


def fx_base(fee: FeeSchedule, amount: Decimal, used: Usage | None) -> tuple[Decimal, str | None]:
    """Amount the FX fee applies to. With an exchange allowance only the excess is charged ("für den zusätzlichen
    Betrag"); unknown usage counts as used up."""
    if fee.fx_free_eur is None:
        return amount, None
    if used is None or used.fx_eur is None:
        return amount, "Wechsellimit als verbraucht angenommen (bisheriger Umtausch nicht angegeben)"
    left = max(ZERO, fee.fx_free_eur - used.fx_eur)
    return max(ZERO, amount - left), f"Wechsellimit {fee.fx_free_eur} EUR, bisher {used.fx_eur} EUR umgetauscht"


def cost_line(label: str, fee: FeeSchedule | None, s: Scenario) -> CostLine:
    if fee is None:
        return CostLine(label=label, missing=["fee document"])
    comps: dict[str, Decimal] = {}
    missing: list[str] = []
    notes: list[str] = []
    if s.kind == "cash":
        if fee.percent is None and fee.min_eur is None:
            missing.append("cash_fee")
        else:
            free, note = allowance(fee, s.amount_eur, s.usage_for(label))
            comps["cash_fee"] = ZERO if free else cash_cost(fee, s.amount_eur)
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


def matrix(fees: dict[str, FeeSchedule | None], kind: str, country: str, max_amount: int = 2000):
    """Winner bands [(from_eur, to_eur, label)] over whole-euro amounts."""
    # shortcut: 1-EUR scan instead of solving the piecewise-linear crossovers; exact enough for advice up to ~10k EUR
    bands: list[tuple[int, int, str]] = []
    for amount in range(1, max_amount + 1):
        best = rank(fees, Scenario(kind=kind, amount_eur=Decimal(amount), country=country))[0]
        winner = best.label if best.total is not None else "unknown"
        if bands and bands[-1][2] == winner:
            bands[-1] = (bands[-1][0], amount, winner)
        else:
            bands.append((amount, amount, winner))
    return bands
