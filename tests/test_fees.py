import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from cardcost import fees
from cardcost.fees import fee_passages, read_fees, update_fees
from cardcost.ingest import ingest_paths
from cardcost.models import FeeSchedule
from cardcost.retrieval import Retriever

ROOT = Path(__file__).parent.parent
ROW = "Bargeldauszahlung am Geldautomaten | 3,0 % mind. 6,00 EUR | 1,0 % mind. 7,50 EUR"


def _item(product, pct, mn):
    return {
        "product": product,
        "percent": pct,
        "min_eur": mn,
        "currency": "EUR",
        "conditions": None,
        "fx_percent": None,
        "atm_operator_fee_eur": None,
        "cash_interest_pa": None,
        "free_count": None,
        "free_amount_eur": None,
        "free_from_eur": None,
        "fx_free_eur": None,
        "source_file": "beta_card.pdf",
        "source_page": 1,
        "confidence": 0.9,
        "quote": ROW,
        "not_stated": [],
    }


class FakeLLM:
    calls = 0

    def create(self, purpose, prompt_version, **kw):
        self.calls += 1
        assert ROW in kw["messages"][0]["content"]  # the fee table reaches the extractor
        products = [_item("Beta Classic", "3.0", "6.00"), _item("Beta Gold", "1.0", "7.50")]
        return {"content": [{"type": "tool_use", "name": "record_fees", "input": {"products": products}}]}


@pytest.fixture
def conn():
    from cardcost import db

    return db.connect(":memory:")


def test_extract_once_and_unchanged_sources_change_nothing(tmp_path, conn):
    pdf = tmp_path / "beta_card.pdf"
    shutil.copy(ROOT / "samples/beta_card.pdf", pdf)
    out, llm = tmp_path / "fees.json", FakeLLM()
    assert update_fees([pdf], out, llm, conn, "bm25") == ["beta_card"]
    first = out.read_bytes()
    assert [f.product for f in read_fees([out])["beta_card"]] == ["Beta Classic", "Beta Gold"]
    assert update_fees([pdf], out, llm, conn, "bm25") == []
    assert (llm.calls, out.read_bytes()) == (1, first)
    pdf.write_bytes(pdf.read_bytes() + b"\n%changed")  # a changed source is extracted again
    assert update_fees([pdf], out, llm, conn, "bm25") == ["beta_card"]
    assert llm.calls == 2


def test_card_without_fees_is_retried(tmp_path, conn):
    pdf = tmp_path / "beta_card.pdf"
    shutil.copy(ROOT / "samples/beta_card.pdf", pdf)
    out = tmp_path / "fees.json"

    class Nothing:
        def create(self, *a, **kw):
            return {"content": []}

    update_fees([pdf], out, Nothing(), conn, "bm25")
    assert update_fees([pdf], out, FakeLLM(), conn, "bm25") == ["beta_card"]


def test_stored_fee_keeps_the_quote_validation(tmp_path):
    out = tmp_path / "fees.json"
    fee = json.loads(FeeSchedule(card="beta_card", **_item("Beta Gold", "1.0", "7.50")).model_dump_json())
    out.write_text(json.dumps({"beta_card": {"fees": [fee | {"percent": "9.9"}]}}))  # number not in the quote
    with pytest.raises(ValidationError):
        read_fees([out])


def test_missing_fees_file_says_how_to_create_it(tmp_path):
    with pytest.raises(RuntimeError, match="cardcost ingest"):
        read_fees([tmp_path / "nope.json"])


def test_context_grows_with_document_size():
    from cardcost.models import Passage

    big = [
        Passage(id=f"big:p{i}:0", card_id="big", file="big.pdf", page=i, text=f"Bargeld Seite {i}")
        for i in range(1, 13)
    ]
    beta = ingest_paths([ROOT / "samples/beta_card.pdf"])
    r = Retriever(big + beta, mode="bm25")
    assert (len(fee_passages(r, "big")), len(fee_passages(r, "beta_card")) <= 3) == (4, True)


def test_fee_query_reaches_revolut_fx_section():
    # Revolut calls its FX fee "Wechselgebühr" / "Wechsellimit" (p5); the fee-terms query must find it
    rev = ingest_paths([ROOT / "catalog/docs/revolut_standard.pdf"])
    assert 5 in {p.page for p in fee_passages(Retriever(rev, mode="bm25"), "revolut_standard")}


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
        "--mode",
        "bm25",
    ]
    assert cardcost.cli.main(argv) == 0
    assert set(json.loads(out.read_text())) == {"beta_card"}


def test_failed_extraction_keeps_the_old_fees(tmp_path, conn):
    pdf = tmp_path / "beta_card.pdf"
    shutil.copy(ROOT / "samples/beta_card.pdf", pdf)
    out = tmp_path / "fees.json"
    update_fees([pdf], out, FakeLLM(), conn, "bm25")
    before = out.read_bytes()
    pdf.write_bytes(pdf.read_bytes() + b"\n%changed")

    class Nothing:
        def create(self, *a, **kw):
            return {"content": []}

    update_fees([pdf], out, Nothing(), conn, "bm25")
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
        update_fees(pdfs, out, DiesOnSecond(), conn, "bm25")
    assert set(json.loads(out.read_text())) == {"beta_card"}
    assert update_fees(pdfs, out, ok, conn, "bm25") == ["other_card"]  # resumes with the missing card only
