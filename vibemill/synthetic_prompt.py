"""Synthetic prompt generation (Bundle G).

The 60% non-news pipeline calls Claude Haiku here to produce a single
hackathon-style project idea, conditioned on a track from tracks.py.
The output is a NewsItem-shaped object so the downstream pipeline
(guard -> matcher -> generator) operates identically on news and
synthetic inputs.

Why Claude Haiku and not DeepSeek V4 Flash: Claude is more trained
on American hackathon culture (the cohort Vibe Mill targets), and
the synthetic-prompt call is short and inexpensive enough that
Haiku's price (~$1/$5 per M) is a non-issue. ~$0.0005 per synthetic
ideation. See the conversation that produced Bundle G for the rationale.

The synthetic prompt template enforces:
- News-headline-shape so the matcher prompt scores it cleanly
- 6-14 word headlines and 2-4 sentence summaries
- Plausible 24-36 hour hackathon builds
- Implicit form variance (the LLM picks the form that fits the idea)

The orchestrator passes synthetic items through guard + matcher exactly
like news items. If the guard rejects, fine. If the matcher rejects, fine.
The variance over many ticks IS the demonstration.
"""

from __future__ import annotations

import json
import logging
import random
import re
import secrets
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ValidationError

from .clients import openrouter
from .config import get_settings
from .models import NewsItem
from .tracks import TrackChoice

log = logging.getLogger(__name__)

_PROMPT_FILE = "synthetic_prompt.txt"

# Modest token budget — output is JSON with a headline + 2-4 sentence
# summary; should fit in a few hundred tokens.
_MAX_TOKENS = 600

# Calibrated synthetic-prompt archetype distribution. Without a hint, the LLM
# defaults to "tracker for X" because it is the lowest-creativity hackathon
# shape. Real hackathon corpora are much more varied. These weights bias the
# synthetic pipeline toward the actual distribution real college teams pitch.
# Pre-fix the synthetic pipeline produced ~60% trackers; post-fix it should
# match ~12% tracker with the rest spread across chatbot / AI-flavored /
# utility / glorified_* / etc.
# Bundle L: tier-keyed archetype hint distributions. Banger biases toward
# the shapes that actually win Best Overall in 2025-2026 (agentic AI, civic
# tech, collaborative real-time). Slop biases toward derivative shapes
# (glorified_todo, parody_ui) that real abandoned 3am teams ship. Mean_good
# keeps the previously calibrated mid distribution.
_ARCHETYPE_HINT_WEIGHTS_BY_TIER: dict[str, dict[str, float]] = {
    "banger": {
        "ai_agent": 0.20,
        "chatbot": 0.18,
        "tracker": 0.12,
        "ai_generator": 0.10,
        "map_visualizer": 0.08,
        "glorified_social": 0.08,
        "search_directory": 0.07,
        "utility_tool": 0.07,
        "marketplace": 0.05,
        "recommendation_engine": 0.03,
        "glorified_todo": 0.01,
        "game": 0.01,
        "parody_ui": 0.00,
    },
    "mean_good": {
        "chatbot": 0.15,
        "ai_generator": 0.12,
        "tracker": 0.12,
        "ai_agent": 0.10,
        "glorified_todo": 0.10,
        "utility_tool": 0.08,
        "glorified_social": 0.07,
        "marketplace": 0.06,
        "recommendation_engine": 0.05,
        "map_visualizer": 0.05,
        "search_directory": 0.05,
        "game": 0.03,
        "parody_ui": 0.02,
    },
    "slop": {
        "glorified_todo": 0.20,
        "parody_ui": 0.15,
        "tracker": 0.12,
        "glorified_social": 0.10,
        "utility_tool": 0.10,
        "chatbot": 0.08,
        "recommendation_engine": 0.05,
        "game": 0.05,
        "marketplace": 0.04,
        "search_directory": 0.04,
        "ai_generator": 0.03,
        "map_visualizer": 0.02,
        "ai_agent": 0.02,
    },
}

# Tier-emphasis blocks injected into the synthetic prompt. Banger gets
# differentiation guidance and recent real winner exemplars. Slop gets
# permission to be derivative. Mean_good targets subsidiary prize quality.
_TIER_EMPHASIS: dict[str, str] = {
    "banger": (
        "TIER: BANGER. Target Best Overall quality. The idea must have a HOOK:\n"
        "- A SPECIFIC underserved problem named in the inspiration, OR\n"
        "- A SPECIFIC data source or interaction model named in the build, OR\n"
        "- A SPECIFIC novel angle that differentiates from generic shapes.\n"
        "Avoid generic framings like \"tracker for X\" or \"chatbot for Y\" without a hook.\n"
        "The idea should have a concrete user interaction beyond CRUD.\n"
        "Recent banger-class winner shapes, use as inspiration NOT as templates:\n"
        "- HiveMind (TreeHacks 2025 grand prize): AI peer learning agent that detects students struggling silently in Zoom classrooms and forms real time peer learning nodes.\n"
        "- SafeContractor (Civic Tech, Best Overall): scraped seventy thousand contractor license records from obscure public databases, with AI generated credential summaries to flag scammers.\n"
        "- Spent (HackHarvard, Best Financial Hack): predicts spending from your Google Calendar events using Gemini, BEFORE the money leaves your wallet.\n"
        "- TrueFace (HackDartmouth, Best Use of MongoDB): dual sided interview platform with real time deepfake detection on the candidate webcam stream.\n"
        "- Receipt splitter MVP class: receipt OCR plus item level Hungarian assignment debt settlement, settle group debts in minimal transactions.\n"
    ),
    "mean_good": (
        "TIER: MEAN_GOOD. Target subsidiary prize quality (Best UI / Best Tech / Best Use of X / Most Innovative / Best Niche).\n"
        "- Polished in ONE dimension (UI, tech, integration, or niche fit), not all of them.\n"
        "- Specific enough to demo cleanly. Broad enough to leave half the features as TODOs.\n"
        "- Address a relatable college student or young professional problem.\n"
    ),
    "slop": (
        "TIER: SLOP. Target abandoned at 3am quality.\n"
        "- Generic framings are fine. Derivative is fine.\n"
        "- Mock data is canonical.\n"
        "- The idea can be unimpressive. Real exhausted teams ship unimpressive ideas to get any submission in.\n"
    ),
}


def _pick_archetype_hint(tier: str | None = None) -> str:
    """Weighted random archetype hint for the synthetic prompt. Tier biases
    the distribution toward shapes that match the target tier's real world
    win rate. The matcher still runs downstream and may route the prompt
    elsewhere; this just biases the LLM ideation toward the right shape."""
    weights = _ARCHETYPE_HINT_WEIGHTS_BY_TIER.get(tier or "mean_good") or _ARCHETYPE_HINT_WEIGHTS_BY_TIER["mean_good"]
    slugs = list(weights.keys())
    ws = list(weights.values())
    return random.choices(slugs, weights=ws, k=1)[0]


def _tier_emphasis(tier: str | None) -> str:
    """Tier-conditional guidance block injected into the synthetic prompt."""
    return _TIER_EMPHASIS.get(tier or "mean_good", _TIER_EMPHASIS["mean_good"])


class SyntheticPromptError(RuntimeError):
    """The synthetic prompt LLM produced unparseable output twice."""


class _LLMOutput(BaseModel):
    headline: str = Field(..., min_length=4, max_length=500)
    summary: str = Field(..., min_length=8, max_length=2000)


def _track_context(track: TrackChoice) -> str:
    """Render the track context for the prompt template."""
    if track.group == "free_for_all":
        return "free-for-all (no track — any hackathon idea is fine)"
    assert track.display_name is not None
    return f"{track.display_name} (a {track.group.replace('_', ' ')} track)"


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


def _call(user_prompt: str) -> str:
    s = get_settings()
    completion = openrouter.complete(
        model=s.MATCHER_MODEL,  # claude haiku — same as matcher / guard
        messages=[{"role": "user", "content": user_prompt}],
        purpose="synthetic_prompt",
        temperature=0.9,  # higher than matcher: we WANT ideation variance
        response_format_json=True,
        reasoning_effort="disabled",
        app_id=None,  # synthetic prompts pre-date app_id assignment
        max_tokens=_MAX_TOKENS,
    )
    return completion.text or ""


def generate(track: TrackChoice, tier: str | None = None) -> NewsItem:
    """Generate one synthetic hackathon-idea NewsItem.

    Bundle L: when tier is provided, the archetype hint distribution and the
    tier emphasis block are conditioned on it. Banger gets differentiation
    guidance and winner exemplars. Slop gets permission to be derivative.
    Mean_good and unknown tiers fall back to the calibrated mid distribution.

    Raises SyntheticPromptError on two consecutive parse failures.
    """
    archetype_hint = _pick_archetype_hint(tier)
    tier_emphasis = _tier_emphasis(tier)
    user_prompt = (
        _load_prompt()
        .replace("{{track_context}}", _track_context(track))
        .replace("{{archetype_hint}}", archetype_hint)
        .replace("{{tier_emphasis}}", tier_emphasis)
    )
    log.info(
        "synthetic prompt: track=%s/%s tier=%s archetype_hint=%s chars=%d",
        track.group, track.slug or "-", tier or "?", archetype_hint, len(user_prompt),
    )

    for attempt in (1, 2):
        text = _call(user_prompt)
        try:
            parsed = _LLMOutput.model_validate(_extract_json(text))
            log.info(
                "synthetic prompt generated (attempt %d): headline=%r",
                attempt, parsed.headline[:80],
            )
            # Per-generation unique URL so news_cache and AppRecord
            # source_metadata don't collide across synthetic items of the
            # same track.
            uniq = secrets.token_hex(4)
            return NewsItem(
                url=f"https://vibemill.dev/synthetic/{track.slug or 'free'}/{uniq}",
                headline=parsed.headline.strip(),
                summary=parsed.summary.strip(),
                feed_source="synthetic",
                published_at=datetime.now(timezone.utc),
            )
        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            log.warning(
                "synthetic prompt: parse failure attempt %d: %s | text=%r",
                attempt, exc, text[:300],
            )

    raise SyntheticPromptError("synthetic prompt LLM produced unparseable output twice")
