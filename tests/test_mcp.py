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
    choices = {}

    def resolve(self, question, wallet=None):
        return {"beta_card:Gold": GOLD, "gamma_card": None}

    def choice_labels(self):
        return {}

    def scenario(self, s):
        return s

    def missing_facts(self, table):
        return {}


def test_tools_are_read_only_and_compute(monkeypatch):
    monkeypatch.setattr(mcp_server, "_advisor", FakeAdvisor)

    async def run():
        async with Client(mcp_server.mcp) as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
            assert set(tools) == {"get_fee", "compare_cards", "set_wallet_fact"}
            assert all(t.annotations.read_only_hint for n, t in tools.items() if n != "set_wallet_fact")
            fee = await client.call_tool("get_fee", {"card": "beta_card:Gold", "amount_eur": "1000"})
            ranked = await client.call_tool("compare_cards", {"amount_eur": "300", "country": "US"})
            return json.loads(fee.content[0].text), ranked.structured_content or json.loads(ranked.content[0].text)

    fee, ranked = anyio.run(run)
    assert fee["total_eur"] == "10.00"
    assert [(r["card"], r["total_eur"]) for r in (ranked["result"] if isinstance(ranked, dict) else ranked)] == [
        ("beta_card:Gold", "7.50"),
        ("gamma_card", None),
    ]


def test_ambiguous_product_returns_the_choices(monkeypatch):
    class Ambiguous(FakeAdvisor):
        def resolve(self, question, wallet=None):
            assert wallet == ["beta_card:Beta"]  # get_fee prices any card:product, not only wallet entries
            return {"beta_card:Beta": None}

        def choice_labels(self):
            return {"beta_card:Beta": ["beta_card:Beta Classic", "beta_card:Beta Gold"]}

    monkeypatch.setattr(mcp_server, "_advisor", Ambiguous)
    out = mcp_server.get_fee("beta_card:Beta", "300")
    assert out["choose_one_of"] == ["beta_card:Beta Classic", "beta_card:Beta Gold"]
