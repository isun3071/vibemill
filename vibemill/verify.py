"""Verification pass. Deepseek V3 at temperature 0.3 takes the generator's
output, applies the deliberately shallow verifier prompt, and either passes
the files through unchanged or returns edits.

The verifier is **informational, not gating** (per GENERATOR.md v2). It
cannot reject the app. It can only:
- pass the files through unchanged (verdict 'looks good')
- return edits (verdict 'fixed issues')
- declare it found issues it could not fix (verdict 'found issues but unsure how to fix')

If the verifier output is unparseable twice, the orchestrator falls through
with the original generator output and marks verdict='verifier_failed'.
The app still ships.

Per ANTI_PATTERNS.md rule 3, the prompt's shallowness ("check if everything
works") is the satire. Do not improve the prompt.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from pydantic import ValidationError

from .clients import openrouter
from .config import get_settings
from .model_rotation import ModelChoice
from .models import GeneratorOutput, VerifierLLMResult

log = logging.getLogger(__name__)

VERIFIER_TEMPERATURE = 0.3  # see GENERATOR.md "Verifier temperature"
_MAX_TOKENS = 8000

VERDICT_LOOKS_GOOD = "looks good"
VERDICT_FIXED = "fixed issues"
VERDICT_FOUND_BUT_UNSURE = "found issues but unsure how to fix"
VERDICT_FAILED = "verifier_failed"


@dataclass
class VerifyOutcome:
    output: GeneratorOutput  # the files the orchestrator should ship
    verdict: str
    notes: str


def _load_prompt() -> str:
    return (get_settings().prompts_dir / "verifier.txt").read_text()


def _format_files(generated: GeneratorOutput) -> str:
    """Render every file in the generator output as a labeled block for
    the verifier prompt. Bundle D: variable-length file list."""
    parts: list[str] = []
    for f in generated.files:
        parts.append(f"--- {f.path} ---\n{f.content}")
    return "\n".join(parts) if parts else "(no files)"


def _extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object found in response")


def _call(user_prompt: str, *, model: ModelChoice, app_id: str | None) -> str:
    completion = openrouter.complete(
        model=model.slug,
        messages=[{"role": "user", "content": user_prompt}],
        purpose="generator",  # verifier shares the generator model bucket in the cost ledger
        temperature=VERIFIER_TEMPERATURE,
        response_format_json=True,
        reasoning_effort=model.reasoning_effort,
        app_id=app_id,
        max_tokens=_MAX_TOKENS,
    )
    return completion.text or ""


def _normalize_verdict(raw: str) -> str:
    """Map the model's verdict string onto one of the documented buckets.

    The verifier prompt allows free text in `verdict`; this function makes
    the orchestrator's downstream branching robust to surface variation.
    """
    v = (raw or "").strip().lower()
    if "fix" in v:
        return VERDICT_FIXED
    if "unsure" in v or "unfix" in v or "can't" in v or "cannot" in v:
        return VERDICT_FOUND_BUT_UNSURE
    return VERDICT_LOOKS_GOOD


def verify(generated: GeneratorOutput, *, model: ModelChoice, app_id: str | None = None) -> VerifyOutcome:
    """Run the verification pass. Always returns; never raises.

    `model` is the same ModelChoice the generator used for this app; the
    verifier shares the substrate so the within-app fingerprint is coherent
    (one substrate produces both the code and the verifier's attestation).
    """
    user_prompt = _load_prompt().replace("{{generated_files}}", _format_files(generated))

    log.info(
        "==> VERIFIER PROMPT (model=%s reasoning=%s, %d chars including generator output):\n%s\n<== END VERIFIER PROMPT",
        model.slug, model.reasoning_effort, len(user_prompt), user_prompt,
    )
    text = _call(user_prompt, model=model, app_id=app_id)
    try:
        parsed = VerifierLLMResult.model_validate(_extract_json(text))
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        log.warning("verify: malformed JSON, retrying once: %s | text=%r", exc, text[:300])
        text2 = _call(user_prompt, model=model, app_id=app_id)
        try:
            parsed = VerifierLLMResult.model_validate(_extract_json(text2))
        except (json.JSONDecodeError, ValueError, ValidationError) as exc2:
            log.error("verify: second JSON parse failure: %s | text=%r", exc2, text2[:300])
            return VerifyOutcome(
                output=generated,
                verdict=VERDICT_FAILED,
                notes="verifier produced unparseable JSON twice; falling through with the original generator output",
            )

    verdict = _normalize_verdict(parsed.verdict)
    if verdict == VERDICT_FIXED and parsed.files:
        # Use verifier's edited file list. The verifier may add/remove/edit
        # files; we trust its output but still validate against the same
        # path constraints the generator uses (no chassis overwrites, no
        # path traversal). Filtering happens in generator._validate_output;
        # we duplicate it here defensively.
        from .generator import _validate_output as _gen_validate
        try:
            out = _gen_validate(GeneratorOutput(files=parsed.files))
        except ValueError as exc:
            log.warning("verify: 'fixed issues' verdict but file set invalid (%s); falling through to original", exc)
            out = generated
    else:
        # 'looks good', 'found issues but unsure how to fix', or fixed-with-empty-files:
        # ship original.
        out = generated
    return VerifyOutcome(output=out, verdict=verdict, notes=parsed.notes)
