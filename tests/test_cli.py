from decimal import Decimal

from cardcost import db
from cardcost.cli import main
from cardcost.models import FeeSchedule


def test_review_list_and_edit_roundtrip(tmp_path, capsys):
    path = str(tmp_path / "t.db")
    conn = db.connect(path)
    fee = FeeSchedule(card="gamma_card", percent=None, source_file="gamma_card.pdf", source_page=1, confidence=0.9)
    eid = db.save_extraction(conn, fee, status="needs_review", run_id="r", prompt_version="v1")
    assert main(["--db", path, "review", "list"]) == 0
    assert f"#{eid} gamma_card" in capsys.readouterr().out
    rc = main(
        [
            "--db",
            path,
            "review",
            "edited",
            str(eid),
            "--set",
            "percent=2,5",
            "--set",
            "min_eur=4",
            "--quote",
            "2,5 % mindestens 4,00 EUR",
            "--reviewer",
            "ersan",
        ]
    )
    assert rc == 0
    [fixed] = db.reviewed_fees(db.connect(path), "gamma_card")
    assert (fixed.percent, fixed.min_eur) == (Decimal("2.5"), Decimal("4"))
    assert main(["--db", path, "review", "approved", str(eid)]) == 2  # one decision per extraction


def test_wallet(tmp_path, capsys):
    path = str(tmp_path / "t.db")
    assert main(["--db", path, "wallet", "beta_card:Gold", "alpha_card"]) == 0
    assert capsys.readouterr().out.split() == ["alpha_card", "beta_card:Gold"]


def test_ask_usage_only_for_cards_with_an_allowance():
    from decimal import Decimal

    from cardcost.cli import ask_usage
    from cardcost.models import FeeSchedule, Scenario, Usage

    base = dict(source_file="x.pdf", source_page=1, confidence=1.0)
    fees = {
        "c24:Smart": FeeSchedule(
            card="c24", min_eur=Decimal("2.00"), free_count=Decimal("4"), quote="4 x 2,00", **base
        ),
        "rev": FeeSchedule(
            card="rev",
            percent=Decimal("2"),
            free_count=Decimal("5"),
            free_amount_eur=Decimal("200"),
            quote="5 Abhebungen oder 200 €, 2 %",
            **base,
        ),
        "plain": FeeSchedule(card="plain", percent=Decimal("1"), quote="1 %", **base),
        "given": FeeSchedule(card="given", min_eur=Decimal("2"), free_count=Decimal("1"), quote="1 x 2", **base),
    }
    answers = iter(["3", "1", "150,50"])
    asked = []
    cash = Scenario(kind="cash", amount_eur=Decimal("300"))
    used = ask_usage(fees, {"given": Usage(count=0)}, cash, ask=lambda q: asked.append(q) or next(answers))
    assert used == {
        "given": Usage(count=0),
        "c24:Smart": Usage(count=3),
        "rev": Usage(count=1, eur=Decimal("150.50")),
    }
    assert len(asked) == 3 and "4 free" in asked[0]


def test_ask_usage_asks_fx_allowance_only_in_foreign_currency():
    from decimal import Decimal

    from cardcost.cli import ask_usage
    from cardcost.models import FeeSchedule, Scenario, Usage

    rev = FeeSchedule(
        card="rev",
        fx_percent=Decimal("0.5"),
        fx_free_eur=Decimal("1000"),
        quote="1.000 EUR, 0,5 %",
        source_file="x.pdf",
        source_page=1,
        confidence=1.0,
    )
    buy_us = Scenario(kind="purchase", amount_eur=Decimal("100"), country="US")
    assert ask_usage({"rev": rev}, {}, buy_us, ask=lambda q: "400") == {"rev": Usage(count=0, fx_eur=Decimal("400"))}
    buy_fr = Scenario(kind="purchase", amount_eur=Decimal("100"), country="FR")
    assert ask_usage({"rev": rev}, {}, buy_fr, ask=lambda q: 1 / 0) == {}


def test_choose_products_asks_and_saves_the_choice(tmp_path, capsys):
    from cardcost.cli import choose_products

    conn = db.connect(str(tmp_path / "t.db"))
    db.wallet_add(conn, "hvb:Mastercard")
    db.wallet_add(conn, "dkb")

    def f(name):
        return FeeSchedule(card="hvb", product=name, source_file="x.pdf", source_page=1, confidence=1.0)

    options = [f("HVB Mastercard"), f("HVB Mastercard / HVB AktivKonto")]
    fees = {"hvb:Mastercard": None, "dkb": None}
    fees = choose_products(conn, fees, {"hvb:Mastercard": options}, ask=lambda _: "2")
    assert "2) HVB Mastercard / HVB AktivKonto" in capsys.readouterr().out
    assert fees == {"dkb": None, "hvb:HVB Mastercard / HVB AktivKonto": options[1]}
    assert db.wallet(conn) == ["dkb", "hvb:HVB Mastercard / HVB AktivKonto"]  # next question needs no choice


def test_choose_wallet_per_card(capsys):
    from cardcost.cli import choose_wallet

    labels = [
        "dkb:Visa Debit",
        "dkb:Kreditkarte",
        "hvb:HVB Mastercard",
        "hvb:HVB Mastercard / HVB AktivKonto",
        "revolut",
    ]
    answers = iter(["2", "1, 2", ""])  # dkb: Kreditkarte; hvb: both; revolut: not owned
    assert choose_wallet(labels, ask=lambda _: next(answers)) == [
        "dkb:Kreditkarte",
        "hvb:HVB Mastercard",
        "hvb:HVB Mastercard / HVB AktivKonto",
    ]
    out = capsys.readouterr().out
    assert "hvb:\n  1) HVB Mastercard\n  2) HVB Mastercard / HVB AktivKonto" in out and "1) revolut" in out


def test_ingest_record_passes_the_response_file_to_the_llm(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from cardcost import cli

    seen = {}
    monkeypatch.setattr(cli, "LLM", lambda **kw: seen.update(kw))
    monkeypatch.setattr(cli, "update_fees", lambda *a: {})
    cli.cmd_ingest(None, SimpleNamespace(paths=[], fees=str(tmp_path / "f.json"), record=str(tmp_path / "r.json")))
    assert seen["cache_path"] == tmp_path / "r.json"
