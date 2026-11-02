"""All money maths. Decimal only, no floats, no LLM. Each component is rounded half-up to cents, then summed."""

from decimal import Decimal

from cardcost.models import CostLine, FeeSchedule, Scenario
from cardcost.numbers import to_cents

ZERO = Decimal(0)


def cash_cost(fee: FeeSchedule, amount: Decimal) -> Decimal:
    return to_cents(max(amount * (fee.percent or ZERO) / 100, fee.min_eur or ZERO))


def cost_line(label: str, fee: FeeSchedule | None, s: Scenario) -> CostLine:
    if fee is None:
        return CostLine(label=label, missing=["fee document"])
    comps: dict[str, Decimal] = {}
    missing: list[str] = []
    if s.kind == "cash":
        if fee.percent is None and fee.min_eur is None:
            missing.append("cash_fee")
        else:
            comps["cash_fee"] = cash_cost(fee, s.amount_eur)
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
            comps["fx_fee"] = to_cents(s.amount_eur * fee.fx_percent / 100)
    return CostLine(
        label=label,
        components=comps,
        missing=missing,
        total=None if missing else sum(comps.values(), ZERO),
        source=f"{fee.source_file} p.{fee.source_page}",
        quote=fee.quote,
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
