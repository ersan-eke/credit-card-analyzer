"""Read-only MCP server (stdio). Register: claude mcp add cardcost -- uv run --directory <repo> cardcost-mcp"""

from decimal import Decimal
from functools import cache

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from cardcost import db
from cardcost.advisor import Advisor, build_advisor
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
    }


@mcp.tool(annotations=READ_ONLY)
def get_fee(card: str, amount_eur: str) -> dict:
    """Cost of one cash withdrawal in Germany with one card, e.g. card='beta_card:Gold', amount_eur='300'."""
    new_run_id()
    fees = _advisor().resolve(f"Bargeldauszahlung {card}")
    if card not in fees:
        return {"error": f"unknown card {card!r}", "cards": sorted(fees)}
    return _line(cost_line(card, fees[card], Scenario(kind="cash", amount_eur=Decimal(amount_eur))))


@mcp.tool(annotations=READ_ONLY)
def compare_cards(amount_eur: str, country: str) -> list[dict]:
    """Rank all cards for a cash withdrawal of amount_eur in country (ISO code, e.g. 'US'). Unknown fees rank last."""
    new_run_id()
    fees = _advisor().resolve("Bargeldauszahlung Fremdwährung Auslandseinsatzentgelt")
    return [_line(ln) for ln in rank(fees, Scenario(kind="cash", amount_eur=Decimal(amount_eur), country=country))]


def main() -> None:
    setup_logging()  # stderr only: stdout belongs to the MCP protocol
    mcp.run()


if __name__ == "__main__":
    main()
