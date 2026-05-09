"""Matcher: claude haiku scores all 12 archetypes; orchestrator picks one
or rejects.

V0 special case (per MATCHER.md): the matcher prompt still scores all 12
for calibration data, but the orchestrator only ships Tracker apps. If the
random pick from `selected_archetypes` is anything other than 'tracker',
the input is rejected with reason 'archetype not yet implemented'. The
random pick — including the case where Tracker tied with another archetype
and lost the dice roll — is itself satirical content per VOICE.md.
"""

from __future__ import annotations

import json
import logging
import re
import secrets

from pydantic import ValidationError

from .clients import openrouter
from .config import get_settings
from .models import MatcherResult

log = logging.getLogger(__name__)

_PROMPT_FILE = "matcher.txt"
TRACKER = "tracker"


def _load_prompt() -> str:
    return (get_settings().prompts_dir / _PROMPT_FILE).read_text()


def _extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object found in response")


def _call(input_text: str, *, app_id: str | None) -> str:
    s = get_settings()
    user_prompt = _load_prompt().replace("{INPUT}", input_text)
    completion = openrouter.complete(
        model=s.MATCHER_MODEL,
        messages=[{"role": "user", "content": user_prompt}],
        purpose="matcher",
        temperature=0.0,
        response_format_json=True,
        app_id=app_id,
        max_tokens=600,
    )
    return completion.text or ""


def score(input_text: str, *, app_id: str | None = None) -> MatcherResult | None:
    """Score against 12 archetypes. Returns None if both attempts fail to parse."""
    text = _call(input_text, app_id=app_id)
    try:
        return MatcherResult.model_validate(_extract_json(text))
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        log.warning("matcher: malformed JSON, retrying once: %s | text=%r", exc, text[:200])
    text2 = _call(input_text, app_id=app_id)
    try:
        return MatcherResult.model_validate(_extract_json(text2))
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        log.error("matcher: second JSON parse failure: %s | text=%r", exc, text2[:200])
        return None


def pick(result: MatcherResult) -> str | None:
    """Random tiebreak from the matcher's selected archetypes.

    Returns None if `selected_archetypes` is empty (the prompt's signal that
    no archetype scored at or above threshold).
    """
    if not result.selected_archetypes:
        return None
    if len(result.selected_archetypes) == 1:
        return result.selected_archetypes[0]
    return result.selected_archetypes[secrets.randbelow(len(result.selected_archetypes))]


def is_v0_buildable(picked: str | None) -> bool:
    """V0 ships only Tracker apps."""
    return picked == TRACKER
