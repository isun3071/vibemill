"""Matcher: claude haiku scores all 13 archetypes; orchestrator picks
one (or a blended pair) or rejects.

Bundle F revised the taxonomy to 13 form-archetypes and incrementally
expanded the buildable set. Currently buildable: tracker, chatbot,
utility_tool, search_directory. The matcher still scores all 13 for
calibration data; if the random pick lands on a not-yet-implemented
archetype, the input is rejected with reason 'archetype not yet
implemented'. Dice rolling for an unbuildable archetype — including
blend rolls where one side is unbuildable — is itself satirical
content per VOICE.md.

Bundle G adds blend logic: when the top-2 archetype scores are within
1 point of each other AND both >= threshold AND both are in the
buildable set, with probability BLEND_PROBABILITY we return a (primary,
secondary) tuple. The generator gets a "BLEND CONTEXT" preamble for
the secondary; the LLM weaves both forms into one app. Real hackathon
projects often DO blend forms ("a chatbot that recommends restaurants"
is chatbot + recommendation_engine), so this samples the producer-
population's natural form-blending.
"""

from __future__ import annotations

import json
import logging
import random
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
# search_directory. Bundle H adds ai_generator + ai_agent on the Python
# rail (Gradio on HF Spaces). Future bundles add game, marketplace,
# map_visualizer, glorified_todo, glorified_social, recommendation_engine,
# parody_ui.
_V0_BUILDABLE: frozenset[str] = frozenset({
    "tracker",
    "chatbot",
    "utility_tool",
    "search_directory",
    "ai_generator",   # Bundle H: Gradio + HF Spaces
    "ai_agent",       # Bundle H: Gradio + HF Spaces
})

# Public alias for tooling that wants to know what's buildable today
# (e.g. the ship-one CLI's --archetype validation).
V0_BUILDABLE: frozenset[str] = _V0_BUILDABLE

# Bundle G: blend rules.
# When top-2 scores are within BLEND_DELTA of each other AND both >=
# threshold (7) AND both archetypes are buildable, with probability
# BLEND_PROBABILITY the orchestrator generates a 2-archetype blend.
# Otherwise it picks the primary alone.
BLEND_DELTA = 1
BLEND_PROBABILITY = 0.30
SCORE_THRESHOLD = 7


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


def pick_blend(
    result: MatcherResult,
    primary: str,
    *,
    rng: random.Random | None = None,
) -> str | None:
    """Bundle G: maybe return a secondary archetype to blend with primary.

    Returns:
        - None if no blend (single-archetype generation)
        - A buildable archetype slug != primary if a blend was rolled

    Blend rules:
    1. Top-2 scores in the matcher result must both be >= SCORE_THRESHOLD
    2. The two scores must be within BLEND_DELTA of each other
    3. Both archetypes must be in the buildable set (otherwise the
       secondary couldn't actually be incorporated)
    4. Roll: BLEND_PROBABILITY chance of returning the secondary,
       otherwise None
    """
    if primary not in _V0_BUILDABLE:
        return None
    by_score = sorted(result.scores.as_dict().items(), key=lambda kv: -kv[1])
    if len(by_score) < 2:
        return None
    (top_name, top_score), (second_name, second_score) = by_score[0], by_score[1]
    # The primary might have been picked from a tied set; align "top" with it.
    # If primary's score is below top, treat that pair as the candidate.
    primary_score = result.scores.as_dict().get(primary, 0)
    if primary_score < SCORE_THRESHOLD:
        return None
    # Find the highest-scoring buildable archetype that isn't primary.
    for name, score in by_score:
        if name == primary:
            continue
        if score < SCORE_THRESHOLD:
            return None
        if primary_score - score > BLEND_DELTA:
            return None
        if name not in _V0_BUILDABLE:
            return None
        # Eligible secondary found. Roll.
        r = rng or random.Random()
        if r.random() < BLEND_PROBABILITY:
            return name
        return None
    return None


def is_v0_buildable(picked: str | None) -> bool:
    """Whether the orchestrator can ship an app for this archetype.

    Bundle F: tracker, chatbot, utility_tool, search_directory. Other
    archetypes from the 13 score in the matcher (for calibration and the
    "dice rolled wrong" satirical content) but route to rejection.
    """
    return picked in _V0_BUILDABLE
