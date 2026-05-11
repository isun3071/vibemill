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


def generate(track: TrackChoice) -> NewsItem:
    """Generate one synthetic hackathon-idea NewsItem.

    Raises SyntheticPromptError on two consecutive parse failures.
    """
    user_prompt = _load_prompt().replace("{{track_context}}", _track_context(track))
    log.info(
        "synthetic prompt: track=%s/%s chars=%d",
        track.group, track.slug or "-", len(user_prompt),
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
