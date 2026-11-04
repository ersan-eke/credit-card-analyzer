"""Read-only MCP server (stdio). Register: claude mcp add cardcost -- uv run --directory <repo> cardcost-mcp"""

from decimal import Decimal
from functools import cache

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from cardcost import db
from cardcost.advisor import Advisor, build_advisor, parse_usage
from cardcost.calc import cost_line, rank
from cardcost.logs import new_run_id, setup_logging
from cardcost.models import CostLine, Scenario

mcp = MCPServer("cardcost")
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


@cache
def _advisor() -> Advisor:
    return build_advisor(db.connect())


def _line(ln: CostLine) -> dict:
    return {
        "card": ln.label,
        "total_eur": None if ln.total is None else str(ln.total),
        "components": {k: str(v) for k, v in ln.components.items()},
        "not_stated": ln.missing,
        "source": ln.source,
        "quote": ln.quote,
        "notes": ln.notes,
    }


@mcp.tool(annotations=READ_ONLY)
def get_fee(card: str, amount_eur: str, used: list[str] | None = None) -> dict:
    """Cost of one cash withdrawal in Germany with one card, e.g. card='beta_card:Gold', amount_eur='300'.
    An ambiguous product returns choose_one_of: call again with one of those cards.
    used: withdrawals already made this allowance period, e.g. ['c24=2', 'revolut=3:150']; unknown = used up."""
    new_run_id()
    advisor = _advisor()
    fees = advisor.resolve(f"Bargeldauszahlung {card}", wallet=[card])
    if choices := advisor.choice_labels().get(card):
        return {"error": f"ambiguous product {card!r}, call again with one of these", "choose_one_of": choices}
    if card not in fees:
        return {"error": f"unknown card {card!r}", "cards": sorted(fees)}
    return _line(
        cost_line(card, fees[card], Scenario(kind="cash", amount_eur=Decimal(amount_eur), used=parse_usage(used or [])))
    )


@mcp.tool(annotations=READ_ONLY)
def compare_cards(amount_eur: str, country: str, used: list[str] | None = None) -> list[dict]:
    """Rank all cards for a cash withdrawal of amount_eur in country (ISO code, e.g. 'US'). Unknown fees rank last.
    used: withdrawals already made this allowance period, e.g. ['c24=2', 'revolut=3:150']; unknown = used up."""
    new_run_id()
    advisor = _advisor()
    fees = advisor.resolve("Bargeldauszahlung Fremdwährung Auslandseinsatzentgelt")
    choices = advisor.choice_labels()
    return [
        _line(ln) | ({"choose_one_of": choices[ln.label]} if ln.label in choices else {})
        for ln in rank(
            fees, Scenario(kind="cash", amount_eur=Decimal(amount_eur), country=country, used=parse_usage(used or []))
        )
    ]


def main() -> None:
    setup_logging()  # stderr only: stdout belongs to the MCP protocol
    mcp.run()


if __name__ == "__main__":
    main()
