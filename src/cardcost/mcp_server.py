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


def _line(ln: CostLine, asks: dict[str, list[str]] | None = None) -> dict:
    return {
        "card": ln.label,
        "total_eur": None if ln.total is None else str(ln.total),
        "components": {k: str(v) for k, v in ln.components.items()},
        "not_stated": ln.missing,
        "source": ln.source,
        "quote": ln.quote,
        "notes": ln.notes,
        "ask_facts": asks or {},  # fact -> values the user chooses from; save with set_wallet_fact
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
    scenario = advisor.scenario(Scenario(kind="cash", amount_eur=Decimal(amount_eur), used=parse_usage(used or [])))
    line = cost_line(card, fees[card], scenario)
    return _line(line, advisor.missing_facts([line]).get(card))


@mcp.tool(annotations=READ_ONLY)
def compare_cards(amount_eur: str, country: str, used: list[str] | None = None) -> list[dict]:
    """Rank all cards for a cash withdrawal of amount_eur in country (ISO code, e.g. 'US'). Unknown fees rank last.
    used: withdrawals already made this allowance period, e.g. ['c24=2', 'revolut=3:150']; unknown = used up."""
    new_run_id()
    advisor = _advisor()
    fees = advisor.resolve("Bargeldauszahlung Fremdwährung Auslandseinsatzentgelt")
    choices = advisor.choice_labels()
    scenario = advisor.scenario(
        Scenario(kind="cash", amount_eur=Decimal(amount_eur), country=country, used=parse_usage(used or []))
    )
    table = rank(fees, scenario)
    asks = advisor.missing_facts(table)
    return [
        _line(ln, asks.get(ln.label)) | ({"choose_one_of": choices[ln.label]} if ln.label in choices else {})
        for ln in table
    ]


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, idempotent_hint=True, open_world_hint=False))
def set_wallet_fact(card: str, name: str, value: str) -> dict:
    """Save a fact about the user once for a card, e.g. card='hvb', name='account_model', value='HVB AktivKonto'.
    Use the facts and values a cost asks for (ask_facts); 'value:<rule>' saves the user's own price, e.g. '3 EUR'."""
    try:
        _advisor().set_fact(db.connect(), card, name, value)
    except ValueError as e:
        return {"error": str(e)}
    return {"card": card, "name": name, "value": value}


def main() -> None:
    setup_logging()  # stderr only: stdout belongs to the MCP protocol
    mcp.run()


if __name__ == "__main__":
    main()
