"""Wallet facts: set once per card, asked back when a rule needs one, read by CLI, MCP and API alike."""

import json
from decimal import Decimal as D

import anyio
import pytest
from fastapi.testclient import TestClient
from mcp import Client

from cardcost import api, db, mcp_server
from cardcost.advisor import Advisor
from cardcost.cli import ask_facts
from cardcost.models import FeeSchedule, Scenario

MODELS = ["AktivKonto", "PlatinKonto"]


def rule(model: str, price: dict, quote: str) -> dict:
    when = {"facts": {"account_model": [model]}}
    return {"name": "cash_fee", "event": ["atm"], "when": when, "price": price, "quote": quote, "page": 1}


def fees(*rules: dict) -> dict:
    return {"hvb": [FeeSchedule(card="hvb", source_file="h.pdf", source_page=1, confidence=1, rules=list(rules))]}


HVB = fees(
    rule("AktivKonto", {"percent": "1"}, "AktivKonto 1 %"),
    rule("PlatinKonto", {"percent": "0"}, "PlatinKonto kostenlos"),
)
CASH = Scenario(kind="cash", amount_eur=D("300"))


@pytest.fixture
def conn(tmp_path):
    return db.connect(str(tmp_path / "t.db"))


def test_missing_fact_is_asked_for_then_saved_for_the_card(conn):
    a = Advisor(HVB)
    (line,) = a.cost_table("Bargeld", CASH)
    assert line.total is None and line.missing == ["account_model"]
    assert a.missing_facts([line]) == {"hvb": {"account_model": MODELS}}
    a.set_fact(conn, "hvb", "account_model", "AktivKonto")
    assert a.cost_table("Bargeld", CASH)[0].total == D("3.00")
    # persisted: a fresh advisor (another surface, another run) reads the same wallet facts
    again = Advisor(HVB, facts=db.wallet_facts(conn))
    assert again.cost_table("Bargeld", CASH)[0].total == D("3.00")
    assert again.missing_facts(again.cost_table("Bargeld", CASH)) == {}


def test_only_facts_the_rules_declare_are_asked(conn):
    plain = rule("AktivKonto", {"percent": "1"}, "1 %") | {"when": {}}
    a = Advisor(fees(plain))
    assert a.missing_facts(a.cost_table("Bargeld", CASH)) == {}
    with pytest.raises(ValueError, match="no rule needs it"):
        a.set_fact(conn, "hvb", "plan", "Go")


def test_a_fact_value_no_rule_distinguishes_is_refused(conn):
    with pytest.raises(ValueError, match="AktivKonto"):
        Advisor(HVB).set_fact(conn, "hvb", "account_model", "Girokonto")
    assert db.wallet_facts(conn) == {}


def test_own_price_is_a_wallet_fact(conn):
    unstated = rule("AktivKonto", None, "AktivKonto siehe App") | {"when": {}}
    a = Advisor(fees(unstated))
    assert a.cost_table("Bargeld", CASH)[0].missing == ["cash_fee"]
    a.set_fact(conn, "hvb", "value:cash_fee", "3 EUR")
    (line,) = a.cost_table("Bargeld", CASH)
    assert line.total == D("3.00") and line.provided == ["cash_fee"]


def test_cli_asks_the_missing_fact_and_saves_it(conn, capsys):
    a = Advisor(HVB)
    ask_facts(conn, a, a.missing_facts(a.cost_table("Bargeld", CASH)), ask=lambda q: "2")
    assert db.wallet_facts(conn) == {"hvb": {"account_model": "PlatinKonto"}}
    assert "1) AktivKonto" in capsys.readouterr().out


def test_mcp_asks_back_and_saves(conn, monkeypatch):
    monkeypatch.setenv("CARDCOST_DB", str(conn.execute("PRAGMA database_list").fetchone()["file"]))
    advisor = Advisor(HVB, wallet=["hvb"])
    monkeypatch.setattr(mcp_server, "_advisor", lambda: advisor)

    async def run():
        async with Client(mcp_server.mcp) as client:
            call = lambda name, args: client.call_tool(name, args)  # noqa: E731
            asked = json.loads((await call("get_fee", {"card": "hvb", "amount_eur": "300"})).content[0].text)
            bad = json.loads(
                (await call("set_wallet_fact", {"card": "hvb", "name": "account_model", "value": "x"})).content[0].text
            )
            await call("set_wallet_fact", {"card": "hvb", "name": "account_model", "value": "AktivKonto"})
            return asked, bad, json.loads((await call("get_fee", {"card": "hvb", "amount_eur": "300"})).content[0].text)

    asked, bad, answered = anyio.run(run)
    assert asked["total_eur"] is None and asked["ask_facts"] == {"account_model": MODELS}
    assert "error" in bad
    assert answered["total_eur"] == "3.00" and answered["ask_facts"] == {}


def test_api_asks_back_and_saves(tmp_path, monkeypatch):
    monkeypatch.setenv("CARDCOST_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(
        "cardcost.advisor.build_advisor", lambda c: Advisor(HVB, wallet=["hvb"], facts=db.wallet_facts(c))
    )
    monkeypatch.setattr("cardcost.answer.answer", lambda *a: ("text", "template"))
    client = TestClient(api.app)
    ask = lambda: client.get("/ask", params={"q": "300 EUR Bargeld", "kind": "cash"}).json()  # noqa: E731
    first = ask()
    assert first["table"][0]["total"] is None and first["ask_facts"] == {"hvb": {"account_model": MODELS}}
    assert client.put("/wallet/hvb/facts/account_model", params={"value": "Nope"}).status_code == 422
    assert client.put("/wallet/hvb/facts/account_model", params={"value": "PlatinKonto"}).status_code == 200
    second = ask()
    assert D(str(second["table"][0]["total"])) == 0 and second["ask_facts"] == {}
