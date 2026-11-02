import json
import time

import pytest
from fastapi.testclient import TestClient

from cardcost import api


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CARDCOST_WEBHOOK_SECRET", "s3cret")
    monkeypatch.setenv("CARDCOST_DB", str(tmp_path / "t.db"))
    jobs = []
    monkeypatch.setattr(api, "_run_job", jobs.append)
    c = TestClient(api.app)
    c.jobs = jobs
    return c


def _post(client, event, ts=None, secret="s3cret"):
    body = json.dumps(event).encode()
    ts = str(int(ts if ts is not None else time.time()))
    sig = api.sign(secret, ts, body)
    return client.post("/webhooks/new-document", content=body, headers={"X-Timestamp": ts, "X-Signature": sig})


EVENT = {"event_id": "evt-1", "path": "data/private/new.pdf"}


def test_valid_signature_queues_once(client):
    r = _post(client, EVENT)
    assert r.status_code == 200 and r.json()["status"] == "queued"
    again = _post(client, EVENT)
    assert again.status_code == 200 and again.json() == {"status": "duplicate"}
    assert len(client.jobs) == 1


def test_bad_signature(client):
    assert _post(client, EVENT, secret="wrong").status_code == 401


def test_stale_timestamp(client):
    assert _post(client, EVENT, ts=time.time() - 301).status_code == 401


def test_path_outside_inbox_rejected(client):
    assert _post(client, {"event_id": "evt-2", "path": "/etc/passwd.pdf"}).status_code == 400
    assert _post(client, {"event_id": "evt-3", "path": "data/private/../../x.pdf"}).status_code == 400
