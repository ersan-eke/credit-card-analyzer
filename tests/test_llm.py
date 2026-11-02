import anthropic
import httpx2
import pytest

from cardcost import db
from cardcost.llm import LLM, CacheMiss


def _err(cls, status: int, headers: dict | None = None):
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx2.Response(status, headers=headers or {}, request=req), body=None)


class FakeMessages:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def create(self, **kwargs):
        self.calls += 1
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


class FakeResponse:
    stop_reason = "end_turn"

    class usage:  # noqa: N801 - mimics SDK attribute access
        input_tokens, output_tokens = 1000, 200

    def model_dump(self, mode="python"):
        return {
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1000, "output_tokens": 200},
        }


def _llm(outcomes, **kw):
    client = type("C", (), {"messages": FakeMessages(outcomes)})()
    sleeps: list[float] = []
    llm = LLM(client=client, model="test-model", sleep=sleeps.append, **kw)
    return llm, client.messages, sleeps


def test_429_honours_retry_after():
    llm, msgs, sleeps = _llm([_err(anthropic.RateLimitError, 429, {"retry-after": "7"}), FakeResponse()])
    assert llm.create("t", "v1", messages=[])["content"][0]["text"] == "ok"
    assert sleeps == [7.0] and msgs.calls == 2


def test_5xx_backoff_with_bounded_jitter():
    errs = [_err(anthropic.InternalServerError, 503) for _ in range(3)]
    llm, msgs, sleeps = _llm([*errs, FakeResponse()])
    llm.create("t", "v1", messages=[])
    assert len(sleeps) == 3 and all(0 <= s <= 2**i for i, s in enumerate(sleeps))


def test_400_not_retried():
    llm, msgs, sleeps = _llm([_err(anthropic.BadRequestError, 400)])
    with pytest.raises(anthropic.BadRequestError):
        llm.create("t", "v1", messages=[])
    assert msgs.calls == 1 and sleeps == []


def test_gives_up_after_max_retries():
    llm, msgs, _ = _llm([_err(anthropic.InternalServerError, 500) for _ in range(5)])
    with pytest.raises(anthropic.InternalServerError):
        llm.create("t", "v1", messages=[])
    assert msgs.calls == 5


def test_records_tokens_and_cost_and_replays_from_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CARDCOST_PRICE_IN_EUR_PER_MTOK", "2")
    monkeypatch.setenv("CARDCOST_PRICE_OUT_EUR_PER_MTOK", "10")
    conn = db.connect(":memory:")
    cache = tmp_path / "cache.json"
    llm, msgs, _ = _llm([FakeResponse()], conn=conn, cache_path=cache)
    llm.create("extract", "v1", messages=[{"role": "user", "content": "x"}])
    row = conn.execute("SELECT * FROM agent_run").fetchone()
    assert (row["input_tokens"], row["output_tokens"], row["cost_eur"]) == (1000, 200, "0.004")
    replay, msgs2, _ = _llm([], cache_path=cache, live=False)
    assert replay.create("extract", "v1", messages=[{"role": "user", "content": "x"}])["stop_reason"] == "end_turn"
    assert msgs2.calls == 0 and replay.cache_hits == 1
    with pytest.raises(CacheMiss):
        replay.create("extract", "v1", messages=[{"role": "user", "content": "other"}])
