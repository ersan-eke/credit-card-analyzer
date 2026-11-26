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
    reviewer TEXT NOT NULL, edits_json TEXT, fee_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS webhook_event (event_id TEXT PRIMARY KEY, received_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ingest_job (
    id INTEGER PRIMARY KEY, path TEXT, status TEXT DEFAULT 'queued', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS wallet (entry TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS wallet_fact (
    card TEXT NOT NULL, name TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (card, name));
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
    fee_json = fee and fee.model_dump_json()
    product = fee and fee.product
    card = fee.card if fee else card
    same = conn.execute(
        "SELECT id FROM extraction WHERE card IS ? AND product IS ? AND fee_json IS ? AND error IS ?",
        (card, product, fee_json, error),
    ).fetchone()
    if same:  # the same answer for the same document is one review item, not one per question
        return same["id"]
    with conn:
        cur = conn.execute(
            "INSERT INTO extraction (run_id, prompt_version, card, product, fee_json, quote, source_file, page,"
            " confidence, error, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                prompt_version,
                card,
                product,
                fee_json,
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
            "INSERT INTO review (extraction_id, decision, reviewer, edits_json, fee_json) VALUES (?, ?, ?, ?, ?)",
            (extraction_id, decision, reviewer, json.dumps(edits) if edits else None, fee_json),
        )
        conn.execute("UPDATE extraction SET status = ? WHERE id = ?", (decision, extraction_id))


def reviewed_fees(conn, card: str) -> list[FeeSchedule]:
    """Latest human-approved or human-edited values per product of this card; they override extraction."""
    rows = conn.execute(
        "SELECT e.product, r.fee_json FROM review r JOIN extraction e ON e.id = r.extraction_id"
        " WHERE e.card = ? AND r.decision IN ('approved', 'edited') AND r.fee_json IS NOT NULL ORDER BY r.id",
        (card,),
    ).fetchall()
    fees = [FeeSchedule.model_validate_json(r["fee_json"]) for r in rows]
    latest = {f.product: f for f in fees}  # an edit may rename the product, so key on the reviewed values
    return [f.model_copy(update={"confidence": 1.0}) for f in latest.values()]


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


def wallet_set(conn, entries: list[str]) -> None:
    with conn:
        conn.execute("DELETE FROM wallet")
        conn.executemany("INSERT OR IGNORE INTO wallet (entry) VALUES (?)", [(e,) for e in entries])


def wallet_facts(conn) -> dict[str, dict[str, str]]:
    """The facts the user set, per card id."""
    facts: dict[str, dict[str, str]] = {}
    for r in conn.execute("SELECT card, name, value FROM wallet_fact"):
        facts.setdefault(r["card"], {})[r["name"]] = r["value"]
    return facts


def wallet_set_fact(conn, card: str, name: str, value: str) -> None:
    with conn:
        conn.execute("INSERT OR REPLACE INTO wallet_fact (card, name, value) VALUES (?, ?, ?)", (card, name, value))
