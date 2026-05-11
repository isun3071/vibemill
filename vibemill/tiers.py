"""Three-tier output calibration.

Per generation, the orchestrator rolls a single die at fixed weights:

  SLOP       (~10%) — abandoned/late-night/ship-and-forget vibecoder.
                      Hardcoded fabricated data, no web search, single attempt
                      + 1 retry. Reasoning disabled. ~$0.05/app.
  MEAN_GOOD  (~82%) — sub-prize-winning hackathon team (Best UI / Best Tech /
                      Best Use of X / Most Innovative / Best Niche). Polished
                      in one specific dimension. Web search (up to 4 queries)
                      grounds in real data. Reasoning at LOW for cross-file
                      coherence. ~$0.40/app.
  BANGER     (~8%)  — best-overall hackathon team / committed-QA cohort.
                      Web search (up to 6 queries), reasoning at MEDIUM,
                      4 build attempts. Real data primary, minimal
                      fabrication. ~$0.70/app.

Per ANTI_PATTERNS rule 5 v5 (variance lives at the prompt layer), tier
selection is the effort-allocation axis, archetype/layout/sub-prize-category
are the shape axes, persona is the voice axis. Substrate is fixed (DeepSeek
V4 Flash; reasoning effort varies per tier via model_rotation).

Tier roll is INDEPENDENT of input score, archetype, headline, or any other
signal — purely random sampling of the producer-population distribution.

Bundle E recalibrated MEAN_GOOD upward from "median junior portfolio piece"
to "sub-prize winner". Sub-prize winners polish ONE thing well (UI, or
technical depth, or sponsor integration, or pitch); they don't sweep
"Best Overall" but they do walk away with hardware. This is the target the
60% non-news pipeline (future Bundle G) is calibrated against.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Literal

TierName = Literal["slop", "mean_good", "banger"]

TIER_SLOP: TierName = "slop"
TIER_MEAN_GOOD: TierName = "mean_good"
TIER_BANGER: TierName = "banger"

# (tier, weight). Weights must sum to 1.0.
TIER_WEIGHTS: tuple[tuple[TierName, float], ...] = (
    (TIER_SLOP, 0.10),
    (TIER_MEAN_GOOD, 0.82),
    (TIER_BANGER, 0.08),
)


def _validate_weights() -> None:
    total = sum(w for _, w in TIER_WEIGHTS)
    if not math.isclose(total, 1.0, abs_tol=1e-6):
        raise RuntimeError(f"TIER_WEIGHTS must sum to 1.0 (got {total})")


_validate_weights()


@dataclass(frozen=True)
class TierConfig:
    """Per-tier behavior parameters. Concrete values, no plugin hooks
    (per ANTI_PATTERNS rule 8). Reasoning effort moved to model_rotation
    (Bundle E); it's now tier-driven there, not configured here."""
    tier: TierName
    do_search: bool
    max_search_queries: int
    build_attempts: int  # total attempts, not retries (1 = no retry)
    estimated_cost_usd: float


# Hardcoded per-tier config. Estimated costs are used by the daily-cap
# pre-check; they don't need to be precise, just realistic.
TIER_CONFIGS: dict[TierName, TierConfig] = {
    TIER_SLOP: TierConfig(
        tier=TIER_SLOP,
        do_search=False,
        max_search_queries=0,
        build_attempts=2,
        estimated_cost_usd=0.05,
    ),
    TIER_MEAN_GOOD: TierConfig(
        tier=TIER_MEAN_GOOD,
        do_search=True,
        max_search_queries=4,  # was 3 — sub-prize winners ground harder
        build_attempts=3,       # was 2 — sub-prize winners polish more
        estimated_cost_usd=0.40,  # was 0.30; reasoning=low adds ~$0.05-0.10
    ),
    TIER_BANGER: TierConfig(
        tier=TIER_BANGER,
        do_search=True,
        max_search_queries=6,
        build_attempts=4,
        estimated_cost_usd=0.70,
    ),
}


def pick_tier(*, rng: random.Random | None = None) -> TierName:
    """Roll one tier from the weighted distribution."""
    r = rng or random
    names = [n for n, _ in TIER_WEIGHTS]
    weights = [w for _, w in TIER_WEIGHTS]
    return r.choices(names, weights=weights, k=1)[0]


def get_config(tier: TierName) -> TierConfig:
    return TIER_CONFIGS[tier]
