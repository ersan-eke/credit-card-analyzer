import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from cardcost import fees
from cardcost.fees import read_fees, update_fees
from cardcost.models import FeeSchedule

ROOT = Path(__file__).parent.parent
ROW = "Bargeldauszahlung am Geldautomaten | 3,0 % mind. 6,00 EUR | 1,0 % mind. 7,50 EUR"


def _item(product, pct, mn):
    price = {"percent": pct, "flat_eur": None, "min_eur": mn, "max_eur": None}
    rule = {
        "name": "cash_fee",
        "event": ["atm"],
        "when": {"currency": None, "region": None, "country": None},
        "price": price,
        "allowance": None,
        "stacks": False,
        "quote": ROW,
        "page": 1,
    }
    return {"product": product, "confidence": 0.9, "rules": [rule]}


class FakeLLM:
    calls = 0

    def create(self, purpose, prompt_version, **kw):
        self.calls += 1
        assert ROW in kw["messages"][0]["content"]  # the fee table reaches the extractor
        products = [_item("Beta Classic", "3.0", "6.00"), _item("Beta Gold", "1.0", "7.50")]
        return {"content": [{"type": "tool_use", "name": "record_fees", "input": {"products": products}}]}


@pytest.fixture(autouse=True)
def plain_reader(monkeypatch):
    # the tests change PDFs, so their text is converted again; the plain reader needs no layout extractor
    from cardcost import ingest

    monkeypatch.setattr(ingest, "convert", ingest.read_pdf)


@pytest.fixture
def conn():
    from cardcost import db

    return db.connect(":memory:")


def test_extract_once_and_unchanged_sources_change_nothing(tmp_path, conn):
    pdf = tmp_path / "beta_card.pdf"
    shutil.copy(ROOT / "samples/beta_card.pdf", pdf)
    out, llm = tmp_path / "fees.json", FakeLLM()
    assert update_fees([pdf], out, llm, conn) == {"beta_card": "extracted"}
    first = out.read_bytes()
    assert [f.product for f in read_fees([out])["beta_card"]] == ["Beta Classic", "Beta Gold"]
    assert update_fees([pdf], out, llm, conn) == {}
    assert (llm.calls, out.read_bytes()) == (1, first)
    pdf.write_bytes(pdf.read_bytes() + b"\n%changed")  # a changed source is extracted again
    assert update_fees([pdf], out, llm, conn) == {"beta_card": "extracted"}
    assert llm.calls == 2


def test_card_without_fees_is_retried(tmp_path, conn):
    pdf = tmp_path / "beta_card.pdf"
    shutil.copy(ROOT / "samples/beta_card.pdf", pdf)
    out = tmp_path / "fees.json"

    class Nothing:
        def create(self, *a, **kw):
            return {"content": []}

    update_fees([pdf], out, Nothing(), conn)
    assert update_fees([pdf], out, FakeLLM(), conn) == {"beta_card": "extracted"}


def test_stored_fee_keeps_the_quote_validation(tmp_path):
    out = tmp_path / "fees.json"
    fee = json.loads(
        FeeSchedule(
            card="beta_card", source_file="beta_card.pdf", source_page=1, **_item("Beta Gold", "1.0", "7.50")
        ).model_dump_json()
    )
    fee["rules"][0]["price"]["percent"] = "9.9"  # number not in the quote
    out.write_text(json.dumps({"beta_card": {"fees": [fee]}}))
    with pytest.raises(ValidationError):
        read_fees([out])


def test_missing_fees_file_says_how_to_create_it(tmp_path):
    with pytest.raises(RuntimeError, match="cardcost ingest"):
        read_fees([tmp_path / "nope.json"])


def test_catalog_docs_default_matches_the_catalog():
    assert fees.CATALOG_DOCS == Path("catalog/docs")


def test_cli_ingest_writes_the_fees_file(tmp_path, monkeypatch):
    import cardcost.cli

    monkeypatch.setattr(cardcost.cli, "LLM", lambda conn: FakeLLM())
    out = tmp_path / "fees.json"
    argv = [
        "--db",
        str(tmp_path / "t.db"),
        "ingest",
        str(ROOT / "samples/beta_card.pdf"),
        "--fees",
        str(out),
    ]
    assert cardcost.cli.main(argv) == 0
    assert set(json.loads(out.read_text())) == {"beta_card"}


def test_failed_extraction_keeps_the_old_fees(tmp_path, conn):
    pdf = tmp_path / "beta_card.pdf"
    shutil.copy(ROOT / "samples/beta_card.pdf", pdf)
    out = tmp_path / "fees.json"
    update_fees([pdf], out, FakeLLM(), conn)
    before = out.read_bytes()
    pdf.write_bytes(pdf.read_bytes() + b"\n%changed")

    class Nothing:
        def create(self, *a, **kw):
            return {"content": []}

    update_fees([pdf], out, Nothing(), conn)
    assert out.read_bytes() == before


def test_a_crash_keeps_the_cards_already_extracted(tmp_path, conn):
    pdfs = []
    for name in ("beta_card", "other_card"):
        pdfs.append(tmp_path / f"{name}.pdf")
        shutil.copy(ROOT / "samples/beta_card.pdf", pdfs[-1])
    out, ok = tmp_path / "fees.json", FakeLLM()

    class DiesOnSecond:
        def create(self, *a, **kw):
            if ok.calls:
                raise RuntimeError("429")
            return ok.create(*a, **kw)

    with pytest.raises(RuntimeError):
        update_fees(pdfs, out, DiesOnSecond(), conn)
    assert set(json.loads(out.read_text())) == {"beta_card"}
    assert set(update_fees(pdfs, out, ok, conn)) == {"other_card"}  # resumes with the missing card only


def test_price_list_that_lost_numbers_is_flagged_not_extracted(tmp_path, conn, monkeypatch):
    from cardcost import ingest

    pdf = tmp_path / "beta_card.pdf"
    shutil.copy(ROOT / "samples/beta_card.pdf", pdf)
    monkeypatch.setattr(ingest, "convert", lambda path: [p.replace("7,50", "17,50") for p in ingest.read_pdf(path)])
    llm, out = FakeLLM(), tmp_path / "fees.json"
    assert update_fees([pdf], out, llm, conn) == {"beta_card": "flagged: numbers lost in extraction: 7,50"}
    assert llm.calls == 0 and not out.exists()


def test_converted_text_is_cached_beside_the_pdf_until_it_changes(tmp_path, conn, monkeypatch):
    from cardcost import ingest

    pdf = tmp_path / "beta_card.pdf"
    shutil.copy(ROOT / "samples/beta_card.pdf", pdf)
    converted = []
    monkeypatch.setattr(ingest, "convert", lambda path: converted.append(path) or ingest.read_pdf(path))

    class Nothing:
        def create(self, *a, **kw):
            return {"content": []}

    out = tmp_path / "fees.json"
    update_fees([pdf], out, Nothing(), conn)  # no fees: retried on the next run, from the cached text
    assert ROW in pdf.with_suffix(".md").read_text()
    update_fees([pdf], out, FakeLLM(), conn)
    assert len(converted) == 1
    pdf.write_bytes(pdf.read_bytes() + b"\n%changed")
    update_fees([pdf], out, FakeLLM(), conn)
    assert len(converted) == 2


def test_a_price_list_over_the_token_budget_is_flagged_and_not_sent(tmp_path, conn, monkeypatch):
    from cardcost import extract

    pdf = tmp_path / "beta_card.pdf"
    shutil.copy(ROOT / "samples/beta_card.pdf", pdf)
    monkeypatch.setattr(extract, "MAX_INPUT_TOKENS", 10)
    llm, out = FakeLLM(), tmp_path / "fees.json"
    [(card, status)] = update_fees([pdf], out, llm, conn).items()
    assert card == "beta_card" and status.startswith("flagged: ") and "token budget" in status
    assert llm.calls == 0 and not out.exists()


def test_rules_with_a_bad_quote_are_rejected_not_stored(tmp_path, conn):
    pdf = tmp_path / "beta_card.pdf"
    shutil.copy(ROOT / "samples/beta_card.pdf", pdf)

    class BadQuote(FakeLLM):
        def create(self, *a, **kw):
            response = super().create(*a, **kw)
            for product in response["content"][0]["input"]["products"]:
                product["rules"][0]["quote"] = ROW.replace("3,0", "3,5")  # not in the text
            return response

    out = tmp_path / "fees.json"
    assert update_fees([pdf], out, BadQuote(), conn) == {"beta_card": "no fees found"}
    assert json.loads(out.read_text())["beta_card"]["fees"] == []
