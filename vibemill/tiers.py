"""Three-tier output calibration.

Per generation, the orchestrator rolls a single die at fixed weights:

  SLOP       (~10%) — current behavior preserved. Hardcoded fabricated data,
                      no web search, single attempt + 1 retry. Represents the
                      abandoned/late-night/ship-and-forget vibecoder. ~$0.05/app.
  MEAN_GOOD  (~82%) — NEW DEFAULT. Web search (up to 3 queries) provides
                      real-data foundation. Fabricated metrics + statuses +
                      visual decoration on top. Standard substrate rotation.
                      Represents typical good hackathon team / median junior
                      portfolio piece. ~$0.30/app.
  BANGER     (~8%)  — Web search (up to 6 queries) + reasoning-enabled model
                      + 4 build attempts (3 retries). Real data primary,
                      minimal fabrication. Represents committed-QA cohort.
                      ~$0.70/app.

Per ANTI_PATTERNS rule 5 v4 (sample real-producer variance), this samples
the actual distribution of effort the genre's producer population occupies.
The dice roll is INDEPENDENT of input score, archetype, headline content,
or any other signal — purely random sampling.

The slop tier preserves the original verifier-attesting-to-garbage satirical
content. Tier 2/3 verifier-attesting-to-decent-work is itself genre-faithful
(real vibecoders' Cursor/Claude Code verifiers also rubber-stamp decent work).
The satirical payload shifts from per-app irony to corpus-distribution irony.
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
    (per ANTI_PATTERNS rule 8)."""
    tier: TierName
    do_search: bool
    max_search_queries: int
    build_attempts: int  # total attempts, not retries (1 = no retry)
    force_reasoning: bool
    estimated_cost_usd: float


# Hardcoded per-tier config. Estimated costs are used by the daily-cap
# pre-check; they don't need to be precise, just realistic.
TIER_CONFIGS: dict[TierName, TierConfig] = {
    TIER_SLOP: TierConfig(
        tier=TIER_SLOP,
        do_search=False,
        max_search_queries=0,
        build_attempts=2,
        force_reasoning=False,
        estimated_cost_usd=0.05,
    ),
    TIER_MEAN_GOOD: TierConfig(
        tier=TIER_MEAN_GOOD,
        do_search=True,
        max_search_queries=3,
        build_attempts=2,
        force_reasoning=False,
        estimated_cost_usd=0.30,
    ),
    TIER_BANGER: TierConfig(
        tier=TIER_BANGER,
        do_search=True,
        max_search_queries=6,
        build_attempts=4,
        force_reasoning=True,
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
