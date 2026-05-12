"""README generator with persona rotation.

Real producers don't all write READMEs in the same voice. The 12-persona
pool here samples the distribution real vibecoders occupy: enthusiastic
hackathon dev, terse minimalist, technical-maximalist over-documenter,
formal corporate, gen-z vibes, self-deprecating humble, marketing-loud
LLM-flavored, founder-hustle build-in-public, pretentious academic
register, ironic shitpost, MLH-template-filled-in-at-4am, and grindset
hustle-culture. Per ANTI_PATTERNS.md rule 5 v5, sampling at the prompt
layer is where variance lives now (substrate rotation is gone).

Persona rotation is independent of substrate (model). Bundle E moved
generator + README to a single substrate (DeepSeek V4 Flash); voice
variance is supplied entirely by persona rotation. The same substrate
occasionally produces a corporate README and occasionally a shitpost
README, depending on the dice.

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
from .models import SUBSTRATE_BY_ARCHETYPE

log = logging.getLogger(__name__)


# Bundle H: substrate-aware preface injected before the persona template
# so the LLM doesn't default to Next.js / npm boilerplate for Python apps.
# The persona templates themselves still mention Next.js; this override
# wins because it's later in the prompt and more specific.
_PYTHON_SUBSTRATE_PREFACE = (
    "SUBSTRATE OVERRIDE (Bundle H):\n"
    "This app is a Python Gradio app deployed on Hugging Face Spaces - "
    "NOT a Next.js / TypeScript / Tailwind app. Adapt the README accordingly:\n"
    "- Tech stack: Python, Gradio, plus whichever LLM SDK the app uses "
    "(openai, anthropic, etc.). Do NOT mention Next.js, TypeScript, "
    "Tailwind, React, or npm.\n"
    "- Install block: `pip install -r requirements.txt` (NOT npm install).\n"
    "- Run block: `python app.py` (NOT npm run dev).\n"
    "- Inference: the app uses bring-your-own-key. The reader sets "
    "OPENAI_API_KEY (or ANTHROPIC_API_KEY) in the Space's Settings -> "
    "Secrets. Without the key, the UI loads but inference returns a "
    "placeholder error string.\n"
    "- The chassis README already has a YAML frontmatter block with HF "
    "Spaces metadata (sdk, python_version, sdk_version, app_file). DO "
    "NOT produce another YAML frontmatter block at the top of your "
    "output; your content goes AFTER the existing frontmatter.\n"
    "- The voice and section structure described below still apply; "
    "swap the substrate details only.\n\n"
)

# (persona_name, weight). Weights must sum to 1.0.
# Bundle E rebalanced and added 5 new personas (12 total). The new five
# are founder_hustle, academic, shitpost, mlh_template, and grindset.
README_PERSONAS: tuple[tuple[str, float], ...] = (
    ("enthusiastic", 0.25),
    ("minimalist", 0.15),
    ("mlh_template", 0.07),  # very common: literally the Devpost template
    ("founder_hustle", 0.07),
    ("technical_maximalist", 0.07),
    ("corporate", 0.07),
    ("vibes", 0.07),
    ("humble", 0.07),
    ("chatgpt_loud", 0.05),
    ("academic", 0.05),
    ("shitpost", 0.05),
    ("grindset", 0.03),
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

    `model` is the README's substrate (Bundle E: same slug as the generator
    via model_rotation.readme_model()). `persona` is the README voice,
    picked by pick_persona() — voice variance comes from the 12-persona
    rotation, not from substrate variation.
    """
    user_prompt = _render(
        _load_template(persona),
        app_name=app_name,
        prompt=prompt,
        archetype=archetype,
        source_headline=source_headline,
    )
    # Bundle H: prepend the Python substrate override after the persona
    # template so the LLM swaps Next.js/npm specifics for Gradio/pip ones.
    # The persona's voice and section structure are still followed.
    if SUBSTRATE_BY_ARCHETYPE.get(archetype) == "python":
        user_prompt = user_prompt + "\n\n" + _PYTHON_SUBSTRATE_PREFACE
    log.info(
        "readme prompt: model=%s persona=%s app_name=%s substrate=%s chars=%d",
        model.slug, persona, app_name,
        SUBSTRATE_BY_ARCHETYPE.get(archetype, "js"), len(user_prompt),
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
