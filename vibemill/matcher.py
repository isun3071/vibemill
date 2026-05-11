"""Matcher: claude haiku scores all 13 archetypes; orchestrator picks one
or rejects.

Bundle F revised the taxonomy to 13 form-archetypes and incrementally
expanded the buildable set. Currently buildable: tracker, chatbot,
utility_tool, search_directory. The matcher still scores all 13 for
calibration data; if the random pick lands on a not-yet-implemented
archetype (ai_agent, ai_generator, game, marketplace, map_visualizer,
glorified_todo, glorified_social, recommendation_engine, parody_ui),
the input is rejected with reason 'archetype not yet implemented'.
The dice rolling for an unbuildable archetype — including ties where
a buildable lost the roll — is itself satirical content per VOICE.md.
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

# Archetypes the orchestrator can actually build apps for. Expand as new
# chassis + prompt template pairs are added (see archetypes/ and
# prompts/generator/). Bundle F: tracker + chatbot + utility_tool +
# search_directory. Future bundles add ai_generator, ai_agent, game,
# marketplace, map_visualizer, glorified_todo, glorified_social,
# recommendation_engine, parody_ui.
_V0_BUILDABLE: frozenset[str] = frozenset({
    "tracker",
    "chatbot",
    "utility_tool",
    "search_directory",
})


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
        reasoning_effort="disabled",
        app_id=app_id,
        max_tokens=600,
    )
    return completion.text or ""


def score(input_text: str, *, app_id: str | None = None) -> MatcherResult | None:
    """Score against the 13 archetypes (Bundle F). Returns None if both attempts fail to parse."""
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
    """Whether the orchestrator can ship an app for this archetype.

    Bundle F: tracker, chatbot, utility_tool, search_directory. Other
    archetypes from the 13 score in the matcher (for calibration and the
    "dice rolled wrong" satirical content) but route to rejection.
    """
    return picked in _V0_BUILDABLE
