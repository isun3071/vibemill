"""Guard pass: claude haiku decides whether a prompt is safe to build.

Per MATCHER.md: temperature 0, JSON mode if available, model refusal counts
as a reject (the inheritance pattern). Single retry on malformed JSON; on
second failure, treat as reject with reason "guard parse failure" so we
fail closed.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from .clients import openrouter
from .config import get_settings
from .models import GuardResult

log = logging.getLogger(__name__)

_PROMPT_FILE = "guard.txt"


def _load_prompt() -> str:
    return (get_settings().prompts_dir / _PROMPT_FILE).read_text()


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response.

    Models occasionally wrap JSON in ```json fences or prepend prose; this
    handles both by finding the outermost { ... } span.
    """
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object found in response")


def _looks_like_refusal(text: str) -> bool:
    """Detect when the guard model itself refuses to engage with the input.

    Per MATCHER.md, a refusal is treated as a reject (the inheritance pattern).
    Heuristic: the response does not contain a JSON object AND contains
    common refusal markers.
    """
    if "{" in text and "}" in text:
        return False
    needles = ("i can't", "i cannot", "i'm unable", "i am unable", "i won't")
    lower = text.lower()
    return any(n in lower for n in needles)


def check(input_text: str, *, app_id: str | None = None) -> GuardResult:
    """Run the guard against `input_text`. Return pass/reject."""
    s = get_settings()
    user_prompt = _load_prompt().replace("{INPUT}", input_text)

    completion = openrouter.complete(
        model=s.GUARD_MODEL,
        messages=[{"role": "user", "content": user_prompt}],
        purpose="guard",
        temperature=0.0,
        response_format_json=True,
        app_id=app_id,
        max_tokens=200,
    )
    text = completion.text or ""

    if _looks_like_refusal(text):
        log.info("guard: model refusal -> reject")
        return GuardResult(decision="reject", reason="model refusal")

    try:
        data = _extract_json(text)
        result = GuardResult.model_validate(data)
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        log.warning("guard: malformed JSON, retrying once: %s | text=%r", exc, text[:200])
        # Retry with the malformed output appended
        retry_prompt = (
            user_prompt
            + "\n\nYour previous output was not valid JSON:\n"
            + text[:500]
            + "\n\nReturn the JSON object only, no prose."
        )
        completion2 = openrouter.complete(
            model=s.GUARD_MODEL,
            messages=[{"role": "user", "content": retry_prompt}],
            purpose="guard",
            temperature=0.0,
            response_format_json=True,
            app_id=app_id,
            max_tokens=200,
        )
        text2 = completion2.text or ""
        if _looks_like_refusal(text2):
            return GuardResult(decision="reject", reason="model refusal")
        try:
            data = _extract_json(text2)
            return GuardResult.model_validate(data)
        except (json.JSONDecodeError, ValueError, ValidationError) as exc2:
            log.error("guard: second JSON parse failure: %s | text=%r", exc2, text2[:200])
            # Fail closed.
            return GuardResult(decision="reject", reason="guard parse failure")

    return result
