import hashlib
import hmac
import json
import os
import time
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request

from cardcost import db, ingest
from cardcost.logs import new_run_id, setup_logging

WINDOW_S = 300
INBOX = Path("data/private")  # webhook paths must point inside here; the body is untrusted

setup_logging()
app = FastAPI(title="cardcost")


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def _run_job(job_id: int) -> None:
    ingest.process_job(db.connect(), job_id)


@app.post("/webhooks/new-document")
async def new_document(
    request: Request,
    background: BackgroundTasks,
    x_timestamp: str = Header(...),
    x_signature: str = Header(...),
):
    secret = os.environ.get("CARDCOST_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "webhook secret not configured")
    body = await request.body()
    try:
        fresh = abs(time.time() - int(x_timestamp)) <= WINDOW_S
    except ValueError:
        fresh = False
    if not fresh or not hmac.compare_digest(sign(secret, x_timestamp, body), x_signature):
        raise HTTPException(401, "bad signature or stale timestamp")
    event = json.loads(body)
    path = Path(event["path"]).resolve()
    if not path.is_relative_to(INBOX.resolve()) or path.suffix.lower() != ".pdf":
        raise HTTPException(400, f"path must be a PDF inside {INBOX}/")
    conn = db.connect()
    if not db.remember_event(conn, str(event["event_id"])):
        return {"status": "duplicate"}
    job_id = db.enqueue_ingest(conn, str(path))
    background.add_task(_run_job, job_id)  # runs after the 200 is sent
    return {"status": "queued", "job_id": job_id}


@app.get("/ask")
def ask(
    q: str,
    amount: Decimal | None = None,
    country: str | None = None,
    kind: str | None = None,
    days: int = 0,
    used: Annotated[list[str], Query(description="withdrawals this period, e.g. c24=2 or revolut=3:150")] = [],  # noqa: B006
    wallet: Annotated[list[str], Query(description="cards to compare instead of the saved wallet, e.g. hvb:X")] = [],  # noqa: B006
):
    from cardcost.advisor import build_advisor, parse_scenario, parse_usage
    from cardcost.answer import answer

    run_id = new_run_id()
    conn = db.connect()
    try:
        scenario = parse_scenario(q, amount_eur=amount, country=country, kind=kind, days=days, used=parse_usage(used))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    advisor = build_advisor(conn)
    table = advisor.cost_table(q, scenario, wallet or None)
    text, source = answer(q, advisor.scenario(scenario), table, advisor.fees, advisor.llm)
    return {
        "run_id": run_id,
        "answer": text,
        "answer_source": source,
        "scenario": scenario,
        "table": [line.model_dump() for line in table],
        "choose_product": advisor.choice_labels(),  # ambiguous entries: ask again with wallet=<one of these>
        "ask_facts": advisor.missing_facts(
            table
        ),  # per entry: fact -> values; save with PUT /wallet/{card}/facts/{name}
    }


@app.put("/wallet/{card}/facts/{name}")
def set_fact(card: str, name: str, value: str):
    from cardcost.advisor import build_advisor

    conn = db.connect()
    try:
        build_advisor(conn).set_fact(conn, card, name, value)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"card": card, "name": name, "value": value}
