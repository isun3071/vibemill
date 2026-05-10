"""Layout-archetype rotation within Tracker (Bundle C).

Independent dice roll fired AFTER tier selection and BEFORE generation. The
roll is uncorrelated with substrate, tier, persona, or input score — purely
random sampling.

Per ANTI_PATTERNS rule 5 v4 (sample real-producer variance), substrate
rotation alone produced visual variance within a uniform structural template
(header + 3-5 stat cards + section). Real hackathon teams span 5-8 distinct
layout archetypes depending on what the data and team aesthetic suggest.
This module forces that breadth by sampling layout explicitly.

Layouts (8 total, weights sum to 1.0):
  dashboard       (~30%) — current default; stat cards + section
  long_form       (~15%) — hero + narrative paragraphs + sparse data
  map_dominant    (~15%) — full-bleed map + side panel
  chart_dominant  (~10%) — one big visualization + minimal chrome
  editorial       (~10%) — text-heavy article-style with embedded data
  card_feed       (~10%) — content cards in grid layout (no central counters)
  list_dominant   (~5%)  — table or scrollable list as primary surface
  split_view      (~5%)  — two-column comparison or before/after
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass

log = logging.getLogger(__name__)

LAYOUT_DASHBOARD = "dashboard"
LAYOUT_LONG_FORM = "long_form"
LAYOUT_MAP_DOMINANT = "map_dominant"
LAYOUT_CHART_DOMINANT = "chart_dominant"
LAYOUT_EDITORIAL = "editorial"
LAYOUT_CARD_FEED = "card_feed"
LAYOUT_LIST_DOMINANT = "list_dominant"
LAYOUT_SPLIT_VIEW = "split_view"

# (layout, weight). Weights must sum to 1.0.
LAYOUT_WEIGHTS: tuple[tuple[str, float], ...] = (
    (LAYOUT_DASHBOARD, 0.30),
    (LAYOUT_LONG_FORM, 0.15),
    (LAYOUT_MAP_DOMINANT, 0.15),
    (LAYOUT_CHART_DOMINANT, 0.10),
    (LAYOUT_EDITORIAL, 0.10),
    (LAYOUT_CARD_FEED, 0.10),
    (LAYOUT_LIST_DOMINANT, 0.05),
    (LAYOUT_SPLIT_VIEW, 0.05),
)

LAYOUT_NAMES: frozenset[str] = frozenset(name for name, _ in LAYOUT_WEIGHTS)


@dataclass(frozen=True)
class LayoutChoice:
    name: str


def _validate_weights() -> None:
    total = sum(w for _, w in LAYOUT_WEIGHTS)
    if not math.isclose(total, 1.0, abs_tol=1e-6):
        raise RuntimeError(f"LAYOUT_WEIGHTS must sum to 1.0 (got {total})")


_validate_weights()


def pick_layout(*, rng: random.Random | None = None) -> LayoutChoice:
    """Roll one layout from the weighted distribution."""
    r = rng or random
    names = [n for n, _ in LAYOUT_WEIGHTS]
    weights = [w for _, w in LAYOUT_WEIGHTS]
    name = r.choices(names, weights=weights, k=1)[0]
    return LayoutChoice(name=name)
