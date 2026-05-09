"""Code generator. DeepSeek V3 at temperature 0.7 produces page.tsx + data.ts.

Per ANTI_PATTERNS.md rule 4, the temperature stays at 0.7. Lowering it
would suppress the confident, varied, sometimes-wrong outputs that match
the vibecoding genre. Do not lower.

Per GENERATOR.md, the generator is allowed one retry on malformed JSON.
For build failures, the orchestrator retries the *whole* generator+verify
cycle with the build error appended; that retry is driven by the caller
(see __main__.py), not by this module.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from pydantic import ValidationError

from .clients import openrouter
from .config import get_settings
from .model_rotation import ModelChoice
from .models import GeneratorOutput

log = logging.getLogger(__name__)

GENERATOR_TEMPERATURE = 0.7  # see ANTI_PATTERNS.md rule 4
_MAX_TOKENS = 8000


class GeneratorJSONError(RuntimeError):
    """Both generator attempts produced unparseable JSON."""


def _prompt_path(archetype: str) -> Path:
    return get_settings().prompts_dir / "generator" / f"{archetype}.txt"


def _load_template(archetype: str) -> str:
    path = _prompt_path(archetype)
    if not path.exists():
        raise FileNotFoundError(f"no generator prompt for archetype '{archetype}': {path}")
    return path.read_text()


def _render(template: str, *, prompt: str, source_url: str, source_headline: str, source_summary: str) -> str:
    return (
        template
        .replace("{{prompt}}", prompt)
        .replace("{{source_url}}", source_url)
        .replace("{{source_headline}}", source_headline)
        .replace("{{source_summary}}", source_summary)
    )


def _extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object found in response")


def _call(messages: list[dict], *, model: ModelChoice, app_id: str | None) -> str:
    completion = openrouter.complete(
        model=model.slug,
        messages=messages,
        purpose="generator",
        temperature=GENERATOR_TEMPERATURE,
        response_format_json=True,
        reasoning_effort=model.reasoning_effort,
        app_id=app_id,
        max_tokens=_MAX_TOKENS,
    )
    return completion.text or ""


def generate(
    *,
    archetype: str,
    prompt: str,
    source_url: str,
    source_headline: str,
    source_summary: str,
    model: ModelChoice,
    previous_build_error: str | None = None,
    extra_context: str | None = None,
    app_id: str | None = None,
) -> GeneratorOutput:
    """Run the generator. One retry on malformed JSON.

    `previous_build_error`, if set, signals a build-failure retry: the prompt
    is appended with the error and an instruction to fix it. The caller
    (orchestrator) decides when to do this. Two malformed-JSON failures in
    one call raise GeneratorJSONError.
    """
    template = _load_template(archetype)
    user_prompt = _render(
        template,
        prompt=prompt,
        source_url=source_url,
        source_headline=source_headline,
        source_summary=source_summary,
    )
    if extra_context:
        user_prompt += (
            "\n\nAdditional source material (excerpt from the news article):\n"
            + extra_context
            + "\n\nUse this for richer hardcoded data values and copy. The "
            "data still ships baked into lib/data.ts; this excerpt is just "
            "build-time context for you."
        )
    if previous_build_error:
        user_prompt += (
            "\n\nYour previous output produced a build error. Here is the error:\n"
            + previous_build_error[:2000]
            + "\n\nFix the issue and produce the same JSON structure again."
        )

    log.info(
        "==> GENERATOR PROMPT (model=%s reasoning=%s, archetype=%s, %d chars):\n%s\n<== END GENERATOR PROMPT",
        model.slug, model.reasoning_effort, archetype, len(user_prompt), user_prompt,
    )
    text = _call([{"role": "user", "content": user_prompt}], model=model, app_id=app_id)
    try:
        return GeneratorOutput.model_validate(_extract_json(text))
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        log.warning("generator: malformed JSON, retrying once: %s | text=%r", exc, text[:300])

    retry_prompt = (
        user_prompt
        + "\n\nYour previous output was not valid JSON:\n"
        + text[:1500]
        + "\n\nReturn the JSON object only, no prose, no markdown fences."
    )
    text2 = _call([{"role": "user", "content": retry_prompt}], model=model, app_id=app_id)
    try:
        return GeneratorOutput.model_validate(_extract_json(text2))
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        log.error("generator: second JSON parse failure: %s | text=%r", exc, text2[:300])
        raise GeneratorJSONError("generator failed to produce valid JSON after retry") from exc
