import sqlite3
from decimal import Decimal

import pytest

from cardcost import db
from cardcost.models import FeeSchedule


def _fee(**kw) -> FeeSchedule:
    base = dict(
        card="beta_card",
        product="Beta Classic",
        percent=Decimal("3.0"),
        min_eur=Decimal("6.00"),
        source_file="beta_card.pdf",
        source_page=1,
        confidence=0.5,
        quote="3,0 % mind. 6,00 EUR",
    )
    return FeeSchedule(**(base | kw))


def test_pending_and_one_decision_per_extraction():
    conn = db.connect(":memory:")
    eid = db.save_extraction(conn, _fee(), status="needs_review", run_id="r1", prompt_version="v1")
    db.save_extraction(conn, _fee(confidence=0.95), status="auto", run_id="r1", prompt_version="v1")
    assert [row["id"] for row in db.pending_reviews(conn)] == [eid]
    db.record_decision(conn, eid, "approved", reviewer="ersan")
    assert db.pending_reviews(conn) == []
    with pytest.raises(sqlite3.IntegrityError):
        db.record_decision(conn, eid, "rejected", reviewer="other")


def test_edited_values_win_and_rejected_are_ignored():
    conn = db.connect(":memory:")
    eid = db.save_extraction(conn, _fee(), status="needs_review", run_id="r1", prompt_version="v1")
    assert db.reviewed_fees(conn, "beta_card") == []
    db.record_decision(conn, eid, "edited", reviewer="ersan", edits={"min_eur": "6.50"}, quote="3,0 % mind. 6,50 EUR")
    [fee] = db.reviewed_fees(conn, "beta_card")
    assert fee.min_eur == Decimal("6.50") and fee.confidence == 1.0
    eid2 = db.save_extraction(conn, _fee(product="Beta Gold"), status="needs_review", run_id="r2", prompt_version="v1")
    db.record_decision(conn, eid2, "rejected", reviewer="ersan")
    assert [f.product for f in db.reviewed_fees(conn, "beta_card")] == ["Beta Classic"]


def test_same_extraction_is_saved_once():
    conn = db.connect(":memory:")
    a = db.save_extraction(conn, _fee(), status="needs_review", run_id="r1", prompt_version="v1")
    b = db.save_extraction(conn, _fee(), status="needs_review", run_id="r2", prompt_version="v1")
    assert a == b and len(db.pending_reviews(conn)) == 1


def test_webhook_event_dedup():
    conn = db.connect(":memory:")
    assert db.remember_event(conn, "evt-1") is True
    assert db.remember_event(conn, "evt-1") is False
