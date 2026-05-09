"""OpenRouter chat completion client.

One outbound function: `complete()`. Records a row in `llm_calls` after every
attempt (success or failure) so the cost ledger reflects reality, including
failed-but-billed retries.

Retry policy follows OPERATIONS.md: 3 attempts with exponential backoff
(1s, 2s, 4s). 60s per-call timeout. 100ms quiet pause after every call as
the documented courtesy to OpenRouter's recommended <=1 req/sec.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .. import db
from ..config import get_settings
from ..models import LlmCall, LlmPurpose

log = logging.getLogger(__name__)

_TIMEOUT_S = 60
_PAUSE_AFTER_CALL_S = 0.1


class OpenRouterError(RuntimeError):
    """Any non-2xx response or transport error from OpenRouter."""


@dataclass
class Completion:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    raw: dict[str, Any]


def _record(
    *,
    model: str,
    purpose: LlmPurpose,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    latency_ms: int | None,
    app_id: str | None,
    ok: bool,
) -> None:
    try:
        db.record_llm_call(
            LlmCall(
                model=model,
                purpose=purpose,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                app_id=app_id,
                ok=ok,
            )
        )
    except Exception as exc:  # ledger write must never break the pipeline
        log.warning("llm_calls write failed: %s", exc)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((OpenRouterError, httpx.TransportError)),
)
def _post_chat(
    *, model: str, messages: list[dict[str, Any]], opts: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    s = get_settings()
    payload: dict[str, Any] = {"model": model, "messages": messages, **opts}
    started = time.perf_counter()
    try:
        r = httpx.post(
            f"{s.OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {s.OPENROUTER_API_KEY.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_TIMEOUT_S,
        )
    finally:
        time.sleep(_PAUSE_AFTER_CALL_S)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    if r.status_code >= 500 or r.status_code == 429:
        raise OpenRouterError(f"HTTP {r.status_code} (retryable): {r.text[:300]}")
    if r.status_code != 200:
        # 4xx other than 429: do not retry; auth/payload bug
        raise OpenRouterError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json(), elapsed_ms


def complete(
    *,
    model: str,
    messages: list[dict[str, Any]],
    purpose: LlmPurpose,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    response_format_json: bool = False,
    app_id: str | None = None,
) -> Completion:
    """Send a chat completion request, record cost, return parsed response.

    `response_format_json=True` asks OpenRouter for `response_format=json_object`
    where the model supports it; the orchestrator still validates JSON itself.
    """
    opts: dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None:
        opts["max_tokens"] = max_tokens
    if response_format_json:
        opts["response_format"] = {"type": "json_object"}

    try:
        body, elapsed_ms = _post_chat(model=model, messages=messages, opts=opts)
    except (OpenRouterError, httpx.TransportError, RetryError) as exc:
        # Record the failure with zero cost and tokens so the ledger reflects
        # an attempt was made. Re-raise so the caller can decide what to do.
        _record(
            model=model,
            purpose=purpose,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=None,
            app_id=app_id,
            ok=False,
        )
        log.warning("openrouter call failed (purpose=%s, model=%s): %s", purpose, model, exc)
        raise

    usage = body.get("usage") or {}
    text = body["choices"][0]["message"]["content"] or ""
    tokens_in = int(usage.get("prompt_tokens", 0) or 0)
    tokens_out = int(usage.get("completion_tokens", 0) or 0)
    cost_usd = float(usage.get("cost", 0.0) or 0.0)

    _record(
        model=model,
        purpose=purpose,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        latency_ms=elapsed_ms,
        app_id=app_id,
        ok=True,
    )
    return Completion(
        text=text,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        latency_ms=elapsed_ms,
        raw=body,
    )
