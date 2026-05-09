"""Generator + README model rotation.

Per ANTI_PATTERNS.md rule 5 v4 (sample fingerprint variance the genre's
real human producers actually occupy) and rule 1 v4 (reasoning is allowed
where deliberately configured, asymmetric across the pool).

Per-app:
- pick_generator() rolls one model from the configured pool, weighted
- pick_readme(generator) returns the same model in match_generator mode
  (the app feels like one human used one tool for both), or the fixed
  README_MODEL slug in fixed mode

Each ModelChoice carries the reasoning effort for that slug. Per the v4
rule 1 refinement, only the cheapest pool member (DeepSeek V4 Flash) runs
with reasoning enabled, at medium effort. All other pool members have
reasoning disabled because their effective output price would breach the
hard cap.

Startup-time validate_pool_pricing() hits OpenRouter's catalog, computes
each model's effective output cost (nominal x reasoning multiplier), and
refuses to launch the tick if any exceeds MAX_OUTPUT_PRICE_USD_PER_M.
This catches the "we added a model whose price went up" case without
having to hand-track OpenRouter's pricing.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from typing import Literal

import httpx

from .config import get_settings

log = logging.getLogger(__name__)


ReasoningEffort = Literal["disabled", "low", "medium", "high"]
VALID_EFFORTS: frozenset[str] = frozenset({"disabled", "low", "medium", "high"})

# Effective-cost multipliers vs. nominal completion price. Approximate; the
# point is to catch order-of-magnitude breaches at startup, not to ledger
# costs (the actual usage.cost from OpenRouter populates the cost ledger).
EFFORT_COST_MULTIPLIER: dict[str, float] = {
    "disabled": 1.0,
    "low": 1.5,
    "medium": 3.0,
    "high": 6.0,
}

WEIGHT_SUM_TOLERANCE = 0.01

ROTATION_MODE_MATCH = "match_generator"
ROTATION_MODE_FIXED = "fixed"
VALID_ROTATION_MODES: frozenset[str] = frozenset({ROTATION_MODE_MATCH, ROTATION_MODE_FIXED})

_OPENROUTER_MODELS_TIMEOUT_S = 15


class ModelRotationError(RuntimeError):
    """Pool config or pricing validation failed."""


@dataclass(frozen=True)
class ModelChoice:
    slug: str
    reasoning_effort: ReasoningEffort


@dataclass(frozen=True)
class Pool:
    choices: tuple[ModelChoice, ...]
    weights: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.choices) != len(self.weights):
            raise ModelRotationError(
                f"GENERATOR_MODELS ({len(self.choices)}) and GENERATOR_WEIGHTS "
                f"({len(self.weights)}) must have the same length"
            )
        if not self.choices:
            raise ModelRotationError("GENERATOR_MODELS pool is empty")
        total = sum(self.weights)
        if not math.isclose(total, 1.0, abs_tol=WEIGHT_SUM_TOLERANCE):
            raise ModelRotationError(
                f"GENERATOR_WEIGHTS must sum to 1.0 (got {total:.4f})"
            )
        for c in self.choices:
            if c.reasoning_effort not in VALID_EFFORTS:
                raise ModelRotationError(
                    f"reasoning effort {c.reasoning_effort!r} not in {sorted(VALID_EFFORTS)}"
                )


def _split_csv(field: str, raw: str) -> list[str]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ModelRotationError(f"{field} is empty")
    return parts


def parse_pool() -> Pool:
    """Read GENERATOR_MODELS / WEIGHTS / REASONING_EFFORTS from settings,
    validate, return a frozen Pool. Raises ModelRotationError on any
    misconfiguration."""
    s = get_settings()
    slugs = _split_csv("GENERATOR_MODELS", s.GENERATOR_MODELS)
    raw_weights = _split_csv("GENERATOR_WEIGHTS", s.GENERATOR_WEIGHTS)
    raw_efforts = _split_csv("GENERATOR_REASONING_EFFORTS", s.GENERATOR_REASONING_EFFORTS)

    if not (len(slugs) == len(raw_weights) == len(raw_efforts)):
        raise ModelRotationError(
            f"length mismatch: GENERATOR_MODELS={len(slugs)} "
            f"GENERATOR_WEIGHTS={len(raw_weights)} "
            f"GENERATOR_REASONING_EFFORTS={len(raw_efforts)}"
        )

    try:
        weights = tuple(float(w) for w in raw_weights)
    except ValueError as exc:
        raise ModelRotationError(f"GENERATOR_WEIGHTS contains non-numeric value: {exc}") from exc

    choices = tuple(
        ModelChoice(slug=slug, reasoning_effort=effort)  # type: ignore[arg-type]
        for slug, effort in zip(slugs, raw_efforts)
    )
    return Pool(choices=choices, weights=weights)


def pick_generator(pool: Pool, *, rng: random.Random | None = None) -> ModelChoice:
    """Roll one model from the pool, weighted."""
    r = rng or random
    return r.choices(pool.choices, weights=pool.weights, k=1)[0]


def pick_committed(pool: Pool) -> ModelChoice:
    """Pick the substrate for a committed-path generation.

    Returns the highest-weighted member of the pool whose reasoning_effort
    is not 'disabled'. If no pool member has reasoning enabled, falls back
    to the highest-weighted member overall.

    Per ANTI_PATTERNS rule 1 v4, only deliberately-configured reasoning
    counts as the 'committed' substrate. The default pool has DeepSeek V4
    Flash at medium effort as the highest-weighted reasoning-enabled
    member, so that's what fires by default.

    Deterministic (no RNG): the committed path is itself the random sample;
    its substrate within the path is fixed for fingerprint consistency.
    """
    indices = sorted(
        range(len(pool.choices)),
        key=lambda i: (-pool.weights[i], i),
    )
    for i in indices:
        if pool.choices[i].reasoning_effort != "disabled":
            return pool.choices[i]
    return pool.choices[indices[0]]


def pick_excluding(
    pool: Pool, *, exclude: set[str], rng: random.Random | None = None
) -> ModelChoice:
    """Roll a model from the pool, weighted, excluding the given slugs.

    Used for the rate-limit re-roll path: the generator failed on slug X
    with 429, pick a different one. If exclusion empties the pool, fall
    back to the full pool (one model rate-limited, no point in failing the
    whole app for it).
    """
    r = rng or random
    available_idx = [i for i, c in enumerate(pool.choices) if c.slug not in exclude]
    if not available_idx:
        return pick_generator(pool, rng=rng)
    available_choices = [pool.choices[i] for i in available_idx]
    available_weights = [pool.weights[i] for i in available_idx]
    return r.choices(available_choices, weights=available_weights, k=1)[0]


def pick_readme(generator: ModelChoice, *, mode: str | None = None) -> ModelChoice:
    """Return the README model choice given the generator's choice.

    match_generator: same slug + effort as generator (one substrate per app).
    fixed: README_MODEL with reasoning disabled.
    """
    s = get_settings()
    actual_mode = (mode or s.README_ROTATION_MODE).strip()
    if actual_mode not in VALID_ROTATION_MODES:
        raise ModelRotationError(
            f"README_ROTATION_MODE={actual_mode!r} not in {sorted(VALID_ROTATION_MODES)}"
        )
    if actual_mode == ROTATION_MODE_MATCH:
        return generator
    return ModelChoice(slug=s.README_MODEL, reasoning_effort="disabled")


def fetch_catalog_pricing() -> dict[str, float]:
    """Fetch OpenRouter's model catalog and return a dict of slug -> nominal
    completion price in USD per million output tokens."""
    s = get_settings()
    r = httpx.get(
        f"{s.OPENROUTER_BASE_URL}/models",
        headers={"Authorization": f"Bearer {s.OPENROUTER_API_KEY.get_secret_value()}"},
        timeout=_OPENROUTER_MODELS_TIMEOUT_S,
    )
    if r.status_code != 200:
        raise ModelRotationError(
            f"GET /models failed: HTTP {r.status_code}: {r.text[:300]}"
        )
    pricing: dict[str, float] = {}
    for entry in r.json().get("data", []):
        slug = entry.get("id")
        completion_price_per_token = entry.get("pricing", {}).get("completion")
        if not slug or completion_price_per_token is None:
            continue
        try:
            per_million = float(completion_price_per_token) * 1_000_000
        except (TypeError, ValueError):
            continue
        pricing[slug] = per_million
    return pricing


def validate_pool_pricing(pool: Pool, *, hard_cap_usd_per_m: float | None = None) -> None:
    """Verify each pool model's effective output cost is at or under the
    hard cap. Raises ModelRotationError if any model is missing from the
    OpenRouter catalog or exceeds the cap. Logs effective cost for each
    so the operator can see the pool's composition.
    """
    cap = hard_cap_usd_per_m if hard_cap_usd_per_m is not None else get_settings().MAX_OUTPUT_PRICE_USD_PER_M
    pricing = fetch_catalog_pricing()
    breaches: list[str] = []
    missing: list[str] = []
    for choice in pool.choices:
        nominal = pricing.get(choice.slug)
        if nominal is None:
            missing.append(choice.slug)
            continue
        multiplier = EFFORT_COST_MULTIPLIER[choice.reasoning_effort]
        effective = nominal * multiplier
        log.info(
            "model_rotation: %s reasoning=%s nominal=$%.4f/M effective=$%.4f/M (cap=$%.2f/M)",
            choice.slug, choice.reasoning_effort, nominal, effective, cap,
        )
        if effective > cap:
            breaches.append(
                f"{choice.slug} effective $%.4f/M exceeds cap $%.2f/M (nominal $%.4f/M x %sx)"
                % (effective, cap, nominal, choice.reasoning_effort)
            )
    if missing:
        raise ModelRotationError(
            "model(s) not found in OpenRouter catalog: " + ", ".join(missing)
        )
    if breaches:
        raise ModelRotationError(
            "pool exceeds hard cap: " + "; ".join(breaches)
        )
