"""README generator with persona rotation.

Real producers don't all write READMEs in the same voice. The 7-persona
pool here samples the distribution real vibecoders occupy: enthusiastic
hackathon dev, terse minimalist, technical-maximalist over-documenter,
formal corporate, gen-z vibes, self-deprecating humble, marketing-loud
LLM-flavored. Per ANTI_PATTERNS.md rule 5 v4, sampling that distribution
is faithfulness, not distribution-shaping.

Persona rotation is independent of substrate (model) rotation. The
generator's substrate is matched for within-app fingerprint coherence
(via model_rotation.pick_readme); the persona is rolled separately so
the same substrate occasionally produces a corporate README and
occasionally a vibes README, depending on the dice.

Output is plain markdown, not JSON. No retry: if the LLM's text is empty,
ship the app with an empty README.md (the vibecoder forgot the README).
That is on-brand.
"""

from __future__ import annotations

import logging
import math
import random
from pathlib import Path

from .clients import openrouter
from .config import get_settings
from .model_rotation import ModelChoice

log = logging.getLogger(__name__)

# (persona_name, weight). Weights must sum to 1.0.
README_PERSONAS: tuple[tuple[str, float], ...] = (
    ("enthusiastic", 0.35),
    ("minimalist", 0.20),
    ("technical_maximalist", 0.10),
    ("corporate", 0.10),
    ("vibes", 0.10),
    ("humble", 0.10),
    ("chatgpt_loud", 0.05),
)

VALID_PERSONAS: frozenset[str] = frozenset(name for name, _ in README_PERSONAS)


def _validate_weights() -> None:
    total = sum(w for _, w in README_PERSONAS)
    if not math.isclose(total, 1.0, abs_tol=1e-6):
        raise RuntimeError(
            f"README_PERSONAS weights must sum to 1.0 (got {total})"
        )


_validate_weights()


def pick_persona(*, rng: random.Random | None = None) -> str:
    """Roll a README persona name from the weighted pool."""
    r = rng or random
    names = [n for n, _ in README_PERSONAS]
    weights = [w for _, w in README_PERSONAS]
    return r.choices(names, weights=weights, k=1)[0]


def _persona_path(persona: str) -> Path:
    return get_settings().prompts_dir / "readme" / f"{persona}.txt"


def _load_template(persona: str) -> str:
    if persona not in VALID_PERSONAS:
        raise ValueError(
            f"unknown readme persona {persona!r}; valid: {sorted(VALID_PERSONAS)}"
        )
    return _persona_path(persona).read_text()


def _render(template: str, *, app_name: str, prompt: str, archetype: str, source_headline: str) -> str:
    return (
        template
        .replace("{{app_name}}", app_name)
        .replace("{{prompt}}", prompt)
        .replace("{{archetype}}", archetype)
        .replace("{{source_headline}}", source_headline)
    )


def write(
    *,
    app_name: str,
    prompt: str,
    archetype: str,
    model: ModelChoice,
    persona: str,
    source_headline: str = "",
    app_id: str | None = None,
) -> str:
    """Produce the README.md text for one app. Returns the markdown string.

    `model` is the README's substrate, picked by model_rotation.pick_readme().
    `persona` is the README voice, picked by pick_persona() — independent
    of substrate so the same model occasionally writes corporate and
    occasionally writes vibes.
    """
    user_prompt = _render(
        _load_template(persona),
        app_name=app_name,
        prompt=prompt,
        archetype=archetype,
        source_headline=source_headline,
    )
    log.info(
        "==> README PROMPT (model=%s, persona=%s, app_name=%s, %d chars):\n%s\n<== END README PROMPT",
        model.slug, persona, app_name, len(user_prompt), user_prompt,
    )
    completion = openrouter.complete(
        model=model.slug,
        messages=[{"role": "user", "content": user_prompt}],
        purpose="readme",
        temperature=0.7,
        reasoning_effort=model.reasoning_effort,
        app_id=app_id,
        max_tokens=2000,
    )
    text = (completion.text or "").strip()
    if not text:
        log.warning("readme_writer: empty output; shipping with empty README")
    return text
