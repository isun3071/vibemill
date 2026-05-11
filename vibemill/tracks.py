"""Hackathon-track taxonomy + sampler for the synthetic prompt pipeline.

Bundle G splits orchestrator input 40% news / 60% synthetic. The synthetic
path generates hackathon-style project ideas via Claude Haiku, conditioned
on a track from the taxonomy below.

Tracks are real categories from major college hackathons (HackHarvard,
HackMIT, TreeHacks, PennApps, MHacks — see the web-search done before
Bundle G for the source survey). They describe SUBJECT AREAS, orthogonal
to ARCHETYPES (which describe FORM). A "Healthcare" track could produce
a tracker, a chatbot, a marketplace, a glorified-todo — the track scopes
the idea space; the matcher then routes to the form.

Sampling has two levels: first roll a track GROUP (free-for-all /
cause / tech_frontier / cultural / sponsor_vendor), then if not
free-for-all, roll a named track within the group uniformly.

Free-for-all is its own outcome: no track constraint, the synthetic
prompt is just "any hackathon idea". This matches real hackathons that
have a "Best Overall" category alongside tracked submissions, and it
gives the LLM full latitude to produce off-distribution ideas.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass

log = logging.getLogger(__name__)


# Group weights. Free-for-all + four substantive groups. Must sum to 1.0.
# Sponsor at 7% because it's the most constraining (shoehorns a specific
# vendor product); the others get more room.
TRACK_GROUP_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("free_for_all", 0.30),
    ("cause_based", 0.30),
    ("tech_frontier", 0.25),
    ("cultural_creative", 0.08),
    ("sponsor_vendor", 0.07),
)


# Named tracks per group, from the 2025-2026 hackathon survey. Each track
# is a (slug, display_name) tuple. The slug goes into apps.synthetic_track
# for storage; the display name goes into the synthetic-prompt LLM call.
NAMED_TRACKS: dict[str, tuple[tuple[str, str], ...]] = {
    "cause_based": (
        ("healthcare_wellness", "Healthcare & Wellness"),
        ("sustainability_climate", "Sustainability & Climate"),
        ("education_learning", "Education & Learning"),
        ("accessibility_inclusion", "Accessibility & Inclusion"),
        ("civic_tech", "Civic Tech & Social Impact"),
        ("trust_security", "Trust & Security"),
        ("mental_health", "Mental Health"),
    ),
    "tech_frontier": (
        ("ai_llm", "AI / LLM"),
        ("edge_ai", "Edge AI / On-Device"),
        ("fintech_web3", "Fintech & Web3"),
        ("autonomy_robotics", "Autonomy & Robotics"),
        ("ar_vr_spatial", "AR / VR / Spatial Computing"),
        ("systems_infra", "Systems & Infrastructure"),
        ("dev_tools", "Developer Tools"),
    ),
    "cultural_creative": (
        ("entertainment", "Entertainment & Games"),
        ("culture_storytelling", "Culture & Storytelling"),
        ("creative_tooling", "Creative Tooling"),
        ("music_audio", "Music & Audio"),
    ),
    "sponsor_vendor": (
        ("best_use_of_anthropic", "Best Use of Anthropic API"),
        ("best_use_of_mongodb", "Best Use of MongoDB Atlas"),
        ("best_use_of_vercel", "Best Use of Vercel"),
        ("best_use_of_cerebras", "Best Use of Cerebras"),
        ("best_use_of_fetch_ai", "Best Use of Fetch.ai"),
        ("best_quant_finance", "Best Quant / Finance Application"),
        ("patient_safety", "Patient Safety Technology Challenge"),
    ),
}


@dataclass(frozen=True)
class TrackChoice:
    """A single sampled track."""
    group: str                  # one of TRACK_GROUP_WEIGHTS keys
    slug: str | None            # the named-track slug; None for free_for_all
    display_name: str | None    # the human-readable track name; None for free_for_all


def _validate_weights() -> None:
    total = sum(w for _, w in TRACK_GROUP_WEIGHTS)
    if not math.isclose(total, 1.0, abs_tol=1e-6):
        raise RuntimeError(f"TRACK_GROUP_WEIGHTS must sum to 1.0 (got {total})")


_validate_weights()


def pick_track(*, rng: random.Random | None = None) -> TrackChoice:
    """Roll a track. Two-level sampling: group, then named track within group
    (uniform). Returns TrackChoice with group + slug + display_name; slug
    and display_name are None for free_for_all.
    """
    r = rng or random
    groups = [g for g, _ in TRACK_GROUP_WEIGHTS]
    weights = [w for _, w in TRACK_GROUP_WEIGHTS]
    group = r.choices(groups, weights=weights, k=1)[0]

    if group == "free_for_all":
        return TrackChoice(group=group, slug=None, display_name=None)

    tracks = NAMED_TRACKS[group]
    slug, display = r.choices(tracks, k=1)[0]
    return TrackChoice(group=group, slug=slug, display_name=display)
