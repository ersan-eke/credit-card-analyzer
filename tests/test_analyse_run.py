"""Offline analysis of a recorded run: calls, stop reasons and block types per list, no API call."""

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest
from test_assemble import FEE

from cardcost import db
from cardcost.ingest import READER_VERSION
from cardcost.llm import CacheMiss

EVALS = Path(__file__).parent.parent / "evals"
sys.path.insert(0, str(EVALS))
_spec = importlib.util.spec_from_file_location("analyse_run", EVALS / "analyse_run.py")
ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ar)

QUOTE = "Bargeldauszahlungsentgelt von 2,0 % des Auszahlungsbetrags, mindestens 5,00 EUR."


def _answer(name, payload, tokens):
    return {
        "stop_reason": "tool_use",
        "content": [{"type": "tool_use", "name": name, "input": payload}],
        "usage": {"output_tokens": tokens},
    }


DOC = _answer(
    "record_document", {"cards": [], "conditions": [], "document_for": 0, "card_fee_headings": [], "tables": []}, 21
)
SECTION = _answer(
    "record_section", {"fees": [FEE | {"name": "cash_fee", "event": ["atm"], "percent": "n1", "min_eur": "n2"}]}, 300
)


class FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)

    def create(self, purpose, prompt_version, **kwargs):
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _pdf(tmp_path, name):
    pdf = tmp_path / f"{name}.pdf"
    pdf.write_bytes(name.encode())
    header = f"<!-- cardcost text: sha256={hashlib.sha256(name.encode()).hexdigest()} reader={READER_VERSION} -->"
    pdf.with_suffix(".md").write_text(f"{header}\n<!-- page 1 -->\n{QUOTE}\n")
    return pdf


@pytest.fixture(autouse=True)
def _no_lost(monkeypatch):
    monkeypatch.setattr("cardcost.fees.lost_numbers", lambda path, pages: [])


def test_analyse_reports_calls_stop_reason_and_blocks(tmp_path):
    [row] = ar.analyse([_pdf(tmp_path, "a")], FakeLLM(DOC, SECTION), db.connect(":memory:"), tmp_path / "out.json")
    assert row == ar.Row("a", 2, ["tool_use", "tool_use"], ["tool_use"], 321, "extracted")


def test_truncated_list_is_one_call(tmp_path):
    cut = {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "..."}], "usage": {"output_tokens": 16000}}
    [row] = ar.analyse([_pdf(tmp_path, "a")], FakeLLM(cut), db.connect(":memory:"), tmp_path / "out.json")
    assert (row.calls, row.stop_reasons, row.blocks) == (1, ["max_tokens"], ["text"])
    assert "max_tokens" in row.outcome


def test_unrecorded_list_is_not_called(tmp_path):
    paths = [_pdf(tmp_path, "a"), _pdf(tmp_path, "b")]
    rows = ar.analyse(paths, FakeLLM(CacheMiss("x"), DOC, SECTION), db.connect(":memory:"), tmp_path / "out.json")
    assert [(r.card, r.outcome) for r in rows] == [("a", "not recorded"), ("b", "extracted")]


def test_holdout_rows_print_no_rule_text():
    row = ar.Row("dkb", 2, ["tool_use", "tool_use"], ["tool_use"], 900, "quote not found verbatim on x.pdf page 3")
    line = ar.format_row(row, holdout=True)
    assert "dkb" in line and "2" in line and "900" in line and "quote" in line
    assert "verbatim" not in line and "x.pdf" not in line
    assert "verbatim" in ar.format_row(row, holdout=False)
