"""LLM wrapper: own retry policy, token/cost audit, record/replay cache for evals and CI.

Providers (CARDCOST_PROVIDER): anthropic (default), google (AI Studio) and openrouter. The latter two go through their
OpenAI-compatible /chat/completions endpoint; requests and responses are translated so callers always see the
Anthropic Messages shape."""

import hashlib
import json
import logging
import os
import random
import time
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import anthropic
import httpx2

from cardcost import db
from cardcost.logs import run_id_var

log = logging.getLogger("cardcost.llm")
MAX_RETRIES = 4
BASE_DELAY = 1.0
MAX_DELAY = 30.0


# provider -> (base URL, API-key env var) for OpenAI-compatible endpoints
COMPAT = {
    "google": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/", "OPENROUTER_API_KEY"),
}
_FINISH = {"tool_calls": "tool_use", "length": "max_tokens", "stop": "end_turn", "content_filter": "refusal"}


class CacheMiss(RuntimeError):
    pass


def _retryable(e: Exception) -> bool:
    if isinstance(e, anthropic.APIConnectionError | httpx2.TransportError):
        return True
    if isinstance(e, httpx2.HTTPStatusError):
        status = e.response.status_code
    elif isinstance(e, anthropic.APIStatusError):
        status = e.status_code
    else:
        return False
    return status == 429 or status >= 500


def to_openai(kwargs: dict) -> dict:
    system = [{"role": "system", "content": kwargs["system"]}] if kwargs.get("system") else []
    body = {"model": kwargs["model"], "max_tokens": kwargs["max_tokens"], "messages": system + kwargs["messages"]}
    if kwargs.get("tools"):
        body["tools"] = [
            {
                "type": "function",
                "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]},
            }
            for t in kwargs["tools"]
        ]
        body["tool_choice"] = "auto"
    return body


def from_openai(data: dict) -> dict:
    choice = data["choices"][0]
    message = choice.get("message") or {}
    content = [{"type": "text", "text": message["content"]}] if message.get("content") else []
    for call in message.get("tool_calls") or []:
        raw = call["function"].get("arguments") or "{}"
        try:
            args = json.loads(raw)
        except json.JSONDecodeError:
            args = {"_invalid_json": raw}  # extraction rejects it and retries with the error
        content.append({"type": "tool_use", "id": call.get("id"), "name": call["function"]["name"], "input": args})
    usage = data.get("usage") or {}
    return {
        "content": content,
        "stop_reason": _FINISH.get(choice.get("finish_reason"), choice.get("finish_reason")),
        "usage": {"input_tokens": usage.get("prompt_tokens", 0), "output_tokens": usage.get("completion_tokens", 0)},
    }


def _retry_after(e: Exception) -> float | None:
    response = getattr(e, "response", None)
    value = response.headers.get("retry-after") if response is not None else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None  # shortcut: HTTP-date form of Retry-After is ignored; the API sends seconds


def _cost(input_tokens: int, output_tokens: int) -> Decimal | None:
    price_in = os.environ.get("CARDCOST_PRICE_IN_EUR_PER_MTOK")
    price_out = os.environ.get("CARDCOST_PRICE_OUT_EUR_PER_MTOK")
    if not price_in or not price_out:
        return None
    return (input_tokens * Decimal(price_in) + output_tokens * Decimal(price_out)) / Decimal(1_000_000)


class LLM:
    def __init__(
        self,
        client=None,
        model: str | None = None,
        conn=None,
        cache_path: Path | None = None,
        live: bool = True,
        sleep: Callable[[float], None] = time.sleep,
        provider: str | None = None,
    ):
        self.provider = provider or os.environ.get("CARDCOST_PROVIDER", "anthropic")
        if self.provider != "anthropic" and self.provider not in COMPAT:
            raise RuntimeError(f"CARDCOST_PROVIDER must be anthropic, {' or '.join(COMPAT)}; got {self.provider!r}")
        self.model = model or os.environ.get("CARDCOST_MODEL")
        if not self.model:
            raise RuntimeError("set CARDCOST_MODEL (see .env.example)")
        self._client, self.conn, self.live, self.sleep = client, conn, live, sleep
        self.cache_path = cache_path
        self.cache: dict = json.loads(cache_path.read_text()) if cache_path and cache_path.exists() else {}
        self.calls = self.cache_hits = 0

    @property
    def client(self):
        if self._client is None and self.provider == "anthropic":
            self._client = anthropic.Anthropic(max_retries=0)  # retries are ours, see _call
        elif self._client is None:
            base_url, key_var = COMPAT[self.provider]
            if not os.environ.get(key_var):
                raise RuntimeError(f"set {key_var} for CARDCOST_PROVIDER={self.provider}")
            headers = {"Authorization": f"Bearer {os.environ[key_var]}"}
            self._client = httpx2.Client(base_url=base_url, headers=headers, timeout=300)
        return self._client

    def create(self, purpose: str, prompt_version: str, **kwargs) -> dict:
        """Call messages.create and return the response as a plain dict (same shape live and replayed)."""
        kwargs = {"model": self.model, "max_tokens": 16000} | kwargs
        cache_input = kwargs if self.provider == "anthropic" else {"provider": self.provider} | kwargs
        key = hashlib.sha256(json.dumps(cache_input, sort_keys=True, default=str).encode()).hexdigest()
        if key in self.cache:
            self.cache_hits += 1
            self._audit(purpose, prompt_version, self.cache[key], status="cache")
            return self.cache[key]
        if not self.live:
            raise CacheMiss(f"{purpose}: no recorded response (run the eval with --live to record)")
        response = self._call(kwargs)
        self.calls += 1
        self._audit(purpose, prompt_version, response, status=response.get("stop_reason") or "ok")
        if self.cache_path:
            self.cache[key] = response
            self.cache_path.write_text(json.dumps(self.cache, indent=1, sort_keys=True, ensure_ascii=False))
        return response

    def _call(self, kwargs: dict):
        for attempt in range(MAX_RETRIES + 1):
            try:
                if self.provider == "anthropic":
                    return self.client.messages.create(**kwargs).model_dump(mode="json")
                r = self.client.post("chat/completions", json=to_openai(kwargs))
                r.raise_for_status()
                return from_openai(r.json())
            except Exception as e:
                if not _retryable(e) or attempt == MAX_RETRIES:
                    raise
                delay = _retry_after(e)
                if delay is None:  # full jitter
                    delay = random.uniform(0, min(MAX_DELAY, BASE_DELAY * 2**attempt))
                log.warning("retrying", extra={"attempt": attempt + 1, "delay_s": round(delay, 2), "error": str(e)})
                self.sleep(delay)
        raise AssertionError("unreachable")

    def _audit(self, purpose: str, prompt_version: str, response: dict, status: str) -> None:
        usage = response.get("usage") or {}
        tin, tout = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        cost = Decimal(0) if status == "cache" else _cost(tin, tout)
        log.info(
            "llm_call",
            extra={
                "purpose": purpose,
                "prompt_version": prompt_version,
                "model": f"{self.provider}:{self.model}",
                "input_tokens": tin,
                "output_tokens": tout,
                "cost_eur": cost,
                "status": status,
            },
        )
        if self.conn is not None:
            db.log_run(
                self.conn,
                run_id_var.get(),
                purpose,
                prompt_version,
                f"{self.provider}:{self.model}",
                tin,
                tout,
                cost,
                status,
            )
