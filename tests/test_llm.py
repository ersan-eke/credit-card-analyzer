import json

import anthropic
import httpx2
import pytest

from cardcost import db
from cardcost.llm import LLM, CacheMiss, to_openai


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


TOOL = {"name": "record_fees", "description": "d", "strict": True, "input_schema": {"type": "object"}}


def _compat_llm(provider, handler, **kw):
    client = httpx2.Client(transport=httpx2.MockTransport(handler), base_url="https://compat.example/v1/")
    sleeps: list[float] = []
    return LLM(client=client, model="some/model", provider=provider, sleep=sleeps.append, **kw), sleeps


@pytest.mark.parametrize("provider", ["openrouter", "google"])
def test_openai_compatible_providers_translate_tool_calls(provider):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {"name": "record_fees", "arguments": '{"products": []}'},
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 7},
            },
        )

    llm, _ = _compat_llm(provider, handler)
    out = llm.create(
        "extract",
        "v1",
        system="SYS",
        tools=[TOOL],
        tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": "hi"}],
    )
    body = seen[0]
    assert body["messages"][0] == {"role": "system", "content": "SYS"}
    assert body["tools"][0]["function"]["parameters"] == {"type": "object"} and body["tool_choice"] == "auto"
    assert "strict" not in json.dumps(body["tools"])  # Anthropic-only field
    assert out == {
        "content": [{"type": "tool_use", "id": "c1", "name": "record_fees", "input": {"products": []}}],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 50, "output_tokens": 7},
    }


def test_openai_compatible_retries_429_with_retry_after():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx2.Response(429, headers={"retry-after": "3"})
        return httpx2.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "ok"}}]})

    llm, sleeps = _compat_llm("openrouter", handler)
    assert llm.create("answer", "v1", messages=[])["content"] == [{"type": "text", "text": "ok"}]
    assert sleeps == [3.0]


def test_openai_compatible_400_not_retried():
    llm, sleeps = _compat_llm("google", lambda r: httpx2.Response(400, json={"error": "bad schema"}))
    with pytest.raises(httpx2.HTTPStatusError):
        llm.create("answer", "v1", messages=[])
    assert sleeps == []


def test_unknown_provider_rejected():
    with pytest.raises(RuntimeError, match="CARDCOST_PROVIDER"):
        LLM(model="m", provider="nope")


def test_compat_providers_get_the_forced_tool_and_the_temperature():
    body = to_openai(
        {
            "model": "m",
            "max_tokens": 1,
            "messages": [],
            "tools": [{"name": "t", "description": "d", "input_schema": {"type": "object"}}],
            "tool_choice": {"type": "any"},
            "temperature": 0,
        }
    )
    assert body["tool_choice"] == "required" and body["temperature"] == 0


def test_anthropic_requests_carry_no_temperature():
    seen = {}

    class Messages:
        def create(self, **kwargs):
            seen.update(kwargs)
            return FakeResponse()

    llm = LLM(client=type("C", (), {"messages": Messages()})(), model="test-model")
    llm.create("extract", "v", messages=[], temperature=0)
    assert "temperature" not in seen


def test_a_model_that_rejects_the_forced_tool_is_asked_again_without_it():
    seen = []

    class Messages:
        def create(self, **kwargs):
            seen.append(kwargs)
            if "tool_choice" in kwargs:
                req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
                message = 'tool_choice: type "tool" and "any" are not supported for this model.'
                raise anthropic.BadRequestError(
                    "bad", response=httpx2.Response(400, request=req), body={"error": {"message": message}}
                )
            return FakeResponse()

    llm = LLM(client=type("C", (), {"messages": Messages()})(), model="m")
    llm.create("extract", "v", messages=[], tool_choice={"type": "any"})
    assert ["tool_choice" in k for k in seen] == [True, False]


def _bad_request(message):
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.BadRequestError(
        "bad", response=httpx2.Response(400, request=req), body={"error": {"message": message}}
    )


def test_other_400s_about_the_forced_tool_are_raised_and_the_drop_is_logged(caplog):
    llm, msgs, _ = _llm([_bad_request("tool_choice: unknown tool name record_fee")])
    with pytest.raises(anthropic.BadRequestError):
        llm.create("extract", "v", messages=[], tool_choice={"type": "any"})
    assert msgs.calls == 1
    llm, msgs, _ = _llm([_bad_request('tool_choice: type "any" is not supported for this model'), FakeResponse()])
    with caplog.at_level("WARNING", logger="cardcost.llm"):
        llm.create("extract", "v", messages=[], tool_choice={"type": "any"})
    assert "tool_choice_dropped" in caplog.text
