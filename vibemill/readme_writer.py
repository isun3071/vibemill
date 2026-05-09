"""Vibecoder-persona README generator. Claude haiku writes from the
fictional solo-developer perspective described in PERSONAS.md.

Per ANTI_PATTERNS.md rule 7, the README's tells (syntactic over-uniformity,
overshooting self-praise, suspiciously generic 'About the developer'
section, future-work list ending in a self-aware joke) are deliberate.
Do not 'tighten' the persona to read more human.

Output is plain markdown, not JSON. No retry: if the LLM's text is empty,
ship the app with an empty README.md (the vibecoder forgot the README).
That is on-brand.
"""

from __future__ import annotations

import logging

from .clients import openrouter
from .config import get_settings
from .model_rotation import ModelChoice

log = logging.getLogger(__name__)

_PROMPT_FILE = "readme.txt"


def _load_template() -> str:
    return (get_settings().prompts_dir / _PROMPT_FILE).read_text()


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
    source_headline: str = "",
    app_id: str | None = None,
) -> str:
    """Produce the README.md text for one app. Returns the markdown string.

    `model` is the README's substrate, picked by model_rotation.pick_readme().
    Per match_generator mode (default), this matches the app's generator
    model so the README and the code feel like one human used one tool.
    """
    user_prompt = _render(
        _load_template(),
        app_name=app_name,
        prompt=prompt,
        archetype=archetype,
        source_headline=source_headline,
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
