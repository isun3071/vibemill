"""Single-substrate generator + README writer (Bundle E).

ANTI_PATTERNS rule 5 v5 abandoned substrate rotation. Variance now lives
at the prompt layer (layout, archetype, sub-prize-category, README persona);
the LLM substrate is fixed. See ANTI_PATTERNS.md for the rationale.

DeepSeek V4 Flash is the chosen substrate: cheap (input $0.14/M, output
$0.28/M), strong SWE-bench performance, supports reasoning. The README
writer uses the same substrate by default — voice variance is supplied
entirely by README_PERSONAS rotation in readme_writer.py.

The module name stays `model_rotation` for import-compat across callers.
`ModelChoice` is the lone type the rest of the codebase imports; the
old Pool / pick_* / validate_pool_pricing surface is gone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from .config import get_settings

log = logging.getLogger(__name__)


ReasoningEffort = Literal["disabled", "low", "medium", "high"]


@dataclass(frozen=True)
class ModelChoice:
    slug: str
    reasoning_effort: ReasoningEffort


# Tier-driven reasoning effort. Mean_good gets meaningful deliberation
# (medium) for cross-file coherence; banger gets the same medium effort
# but on the larger V4 Pro substrate. Slop runs with reasoning disabled.
_TIER_REASONING: dict[str, ReasoningEffort] = {
    "slop": "disabled",
    "mean_good": "medium",
    "banger": "medium",
}

# Per-tier generator model overrides. Tiers not listed fall through to
# settings.GENERATOR_MODEL (currently DeepSeek V4 Flash). Banger uses
# the larger V4 Pro substrate, which on OpenRouter is roughly 2-3x the
# per-token cost of Flash and still well under one cent per app at the
# typical token budgets.
_TIER_GENERATOR_MODEL: dict[str, str] = {
    "banger": "deepseek/deepseek-v4-pro",
}


def generator_model_for_tier(tier: str | None) -> ModelChoice:
    """Return the tier-appropriate generator substrate with reasoning effort.
    Tier-specific model overrides win; otherwise fall back to the
    project-wide GENERATOR_MODEL setting."""
    t = tier or "mean_good"
    slug = _TIER_GENERATOR_MODEL.get(t, get_settings().GENERATOR_MODEL)
    effort: ReasoningEffort = _TIER_REASONING.get(t, "disabled")
    return ModelChoice(slug=slug, reasoning_effort=effort)


def readme_model() -> ModelChoice:
    """Return the README writer substrate (same slug as generator, no reasoning).

    Voice variance is supplied by README persona rotation, not by model choice.
    """
    return ModelChoice(slug=get_settings().GENERATOR_MODEL, reasoning_effort="disabled")
