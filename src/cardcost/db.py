import json
import os
import sqlite3

from cardcost.models import FeeSchedule

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_run (
    id INTEGER PRIMARY KEY, run_id TEXT, purpose TEXT, prompt_version TEXT, model TEXT,
    input_tokens INTEGER, output_tokens INTEGER, cost_eur TEXT, status TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS extraction (
    id INTEGER PRIMARY KEY, run_id TEXT, prompt_version TEXT, card TEXT, product TEXT,
    fee_json TEXT, quote TEXT, source_file TEXT, page INTEGER, confidence REAL, error TEXT,
    status TEXT CHECK (status IN ('auto', 'needs_review', 'approved', 'edited', 'rejected')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS review (
    id INTEGER PRIMARY KEY, extraction_id INTEGER NOT NULL UNIQUE REFERENCES extraction(id),
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'edited', 'rejected')),
    reviewer TEXT NOT NULL, edits_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS webhook_event (event_id TEXT PRIMARY KEY, received_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ingest_job (
    id INTEGER PRIMARY KEY, path TEXT, status TEXT DEFAULT 'queued', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS wallet (entry TEXT PRIMARY KEY);
"""


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or os.environ.get("CARDCOST_DB", "cardcost.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def log_run(conn, run_id, purpose, prompt_version, model, input_tokens, output_tokens, cost_eur, status) -> None:
    with conn:
        conn.execute(
            "INSERT INTO agent_run (run_id, purpose, prompt_version, model, input_tokens, output_tokens, cost_eur,"
            " status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                purpose,
                prompt_version,
                model,
                input_tokens,
                output_tokens,
                None if cost_eur is None else str(cost_eur),
                status,
            ),
        )


def save_extraction(
    conn,
    fee: FeeSchedule | None,
    *,
    status: str,
    run_id: str,
    prompt_version: str,
    card: str | None = None,
    error: str | None = None,
) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO extraction (run_id, prompt_version, card, product, fee_json, quote, source_file, page,"
            " confidence, error, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                prompt_version,
                fee.card if fee else card,
                fee and fee.product,
                fee and fee.model_dump_json(),
                fee and fee.quote,
                fee and fee.source_file,
                fee and fee.source_page,
                fee and fee.confidence,
                error,
                status,
            ),
        )
    return cur.lastrowid


def pending_reviews(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM extraction WHERE status = 'needs_review' ORDER BY id").fetchall()


def record_decision(
    conn,
    extraction_id: int,
    decision: str,
    reviewer: str,
    edits: dict[str, str] | None = None,
    quote: str | None = None,
) -> None:
    """One decision per extraction (UNIQUE). Edits are re-validated through FeeSchedule before saving."""
    row = conn.execute("SELECT * FROM extraction WHERE id = ?", (extraction_id,)).fetchone()
    if row is None:
        raise KeyError(extraction_id)
    fee_json = row["fee_json"]
    if decision == "edited":
        base = json.loads(fee_json) if fee_json else {"card": row["card"], "source_file": "", "source_page": 0}
        fee = FeeSchedule(**(base | (edits or {}) | {"confidence": 1.0, "quote": quote or base.get("quote")}))
        fee_json = fee.model_dump_json()
    with conn:
        conn.execute(
            "INSERT INTO review (extraction_id, decision, reviewer, edits_json) VALUES (?, ?, ?, ?)",
            (extraction_id, decision, reviewer, json.dumps(edits) if edits else None),
        )
        conn.execute("UPDATE extraction SET status = ?, fee_json = ? WHERE id = ?", (decision, fee_json, extraction_id))


def reviewed_fee(conn, card: str, product: str | None) -> FeeSchedule | None:
    """Latest human-approved or human-edited values for this card/product; used instead of re-extracting."""
    row = conn.execute(
        "SELECT fee_json FROM extraction WHERE card = ? AND product IS ? AND status IN ('approved', 'edited')"
        " AND fee_json IS NOT NULL ORDER BY id DESC LIMIT 1",
        (card, product),
    ).fetchone()
    if row is None:
        return None
    fee = FeeSchedule.model_validate_json(row["fee_json"])
    return fee.model_copy(update={"confidence": 1.0})


def remember_event(conn, event_id: str) -> bool:
    """True if new, False if this webhook event was already seen."""
    with conn:
        cur = conn.execute("INSERT OR IGNORE INTO webhook_event (event_id) VALUES (?)", (event_id,))
    return cur.rowcount == 1


def enqueue_ingest(conn, path: str) -> int:
    with conn:
        return conn.execute("INSERT INTO ingest_job (path) VALUES (?)", (path,)).lastrowid


def wallet(conn) -> list[str]:
    return [r["entry"] for r in conn.execute("SELECT entry FROM wallet ORDER BY entry")]


def wallet_add(conn, entry: str) -> None:
    with conn:
        conn.execute("INSERT OR IGNORE INTO wallet (entry) VALUES (?)", (entry,))
