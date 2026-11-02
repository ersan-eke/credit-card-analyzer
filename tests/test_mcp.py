import json
from decimal import Decimal

import anyio
from mcp import Client

from cardcost import mcp_server
from cardcost.models import FeeSchedule

GOLD = FeeSchedule(
    card="beta_card",
    product="Beta Gold",
    percent=Decimal("1.0"),
    min_eur=Decimal("7.50"),
    fx_percent=Decimal("0.00"),
    source_file="beta_card.pdf",
    source_page=1,
    confidence=1,
    quote="1,0 % mind. 7,50 EUR | 0,00 %",
)


class FakeAdvisor:
    def resolve(self, question):
        return {"beta_card:Gold": GOLD, "gamma_card": None}


def test_tools_are_read_only_and_compute(monkeypatch):
    monkeypatch.setattr(mcp_server, "_advisor", FakeAdvisor)

    async def run():
        async with Client(mcp_server.mcp) as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
            assert set(tools) == {"get_fee", "compare_cards"}
            assert all(t.annotations.read_only_hint for t in tools.values())
            fee = await client.call_tool("get_fee", {"card": "beta_card:Gold", "amount_eur": "1000"})
            ranked = await client.call_tool("compare_cards", {"amount_eur": "300", "country": "US"})
            return json.loads(fee.content[0].text), ranked.structured_content or json.loads(ranked.content[0].text)

    fee, ranked = anyio.run(run)
    assert fee["total_eur"] == "10.00"
    assert [(r["card"], r["total_eur"]) for r in (ranked["result"] if isinstance(ranked, dict) else ranked)] == [
        ("beta_card:Gold", "7.50"),
        ("gamma_card", None),
    ]
