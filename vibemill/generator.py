"""Code generator. DeepSeek V3 at temperature 0.7 produces a tier-sized
list of slot files (Bundle D: multi-file generation).

Per ANTI_PATTERNS.md rule 4, the temperature stays at 0.7. Lowering it
would suppress the confident, varied, sometimes-wrong outputs that match
the vibecoding genre. Do not lower.

Per GENERATOR.md, the generator is allowed one retry on malformed JSON.
For build failures, the orchestrator retries the *whole* generator+verify
cycle with the build error appended; that retry is driven by the caller
(see __main__.py), not by this module.

Bundle D file-list contract:
- Output is { "files": [{path, content}, ...] }
- Path validation: must start with 'app/' or 'lib/', must end with .ts/.tsx/.css,
  no path traversal, no absolute paths.
- Chassis-owned paths (app/layout.tsx, app/globals.css) are silently dropped
  if the LLM tries to write them. Chassis wins; rule 10 (the footer
  disclaimer in layout.tsx is non-negotiable).
- app/page.tsx must be present in the validated set. Without it the build
  has no entry point; we surface this as a JSON error to trigger retry.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from pydantic import ValidationError

from .clients import openrouter
from .config import get_settings
from .layouts import LAYOUT_NAMES
from .model_rotation import ModelChoice
from .models import GeneratedFile, GeneratorOutput

log = logging.getLogger(__name__)

GENERATOR_TEMPERATURE = 0.7  # see ANTI_PATTERNS.md rule 4
_MAX_TOKENS = 12000  # raised from 8k for multi-file output
_REQUIRED_PATH = "app/page.tsx"

ALLOWED_PATH_PREFIXES: tuple[str, ...] = ("app/", "lib/")
ALLOWED_EXTENSIONS: tuple[str, ...] = (".ts", ".tsx", ".css")
# Files the chassis owns. The LLM cannot overwrite these — chassis wins.
# layout.tsx carries the Vibe Mill footer (rule 10), and globals.css holds
# the Tailwind directives.
CHASSIS_OWNED_PATHS: frozenset[str] = frozenset({
    "app/layout.tsx",
    "app/globals.css",
})


class GeneratorJSONError(RuntimeError):
    """Both generator attempts produced unparseable JSON or invalid output."""


def _is_valid_slot_path(path: str) -> tuple[bool, str | None]:
    """(ok, reason_if_not). Strict path validation for slot files."""
    if not path or path.startswith("/") or "\\" in path:
        return False, "path must be relative, no backslashes"
    parts = path.split("/")
    if ".." in parts:
        return False, "path traversal not allowed"
    if not any(path.startswith(p) for p in ALLOWED_PATH_PREFIXES):
        return False, f"path must start with {ALLOWED_PATH_PREFIXES}"
    if not any(path.endswith(e) for e in ALLOWED_EXTENSIONS):
        return False, f"file extension must be one of {ALLOWED_EXTENSIONS}"
    return True, None


def _filter_files(files: list[GeneratedFile]) -> list[GeneratedFile]:
    """Drop chassis-owned and invalid paths. Last-write-wins for duplicates.
    Logs every drop with a reason so the operator can see what the LLM tried."""
    by_path: dict[str, GeneratedFile] = {}
    for f in files:
        if f.path in CHASSIS_OWNED_PATHS:
            log.warning("dropping LLM file %s: chassis owns this path", f.path)
            continue
        ok, reason = _is_valid_slot_path(f.path)
        if not ok:
            log.warning("dropping LLM file %s: %s", f.path, reason)
            continue
        if f.path in by_path:
            log.info("duplicate path %s in LLM output; using last", f.path)
        by_path[f.path] = f
    return list(by_path.values())


def _validate_output(out: GeneratorOutput) -> GeneratorOutput:
    """Filter out invalid/chassis-owned files; require app/page.tsx.
    Returns a sanitized GeneratorOutput; raises ValueError if the required
    entry-point file is missing after filtering."""
    valid = _filter_files(out.files)
    if not any(f.path == _REQUIRED_PATH for f in valid):
        raise ValueError(f"output missing required {_REQUIRED_PATH}")
    return GeneratorOutput(files=valid)


# Tier-aware guidance substituted into {{file_count_guidance}} in the prompt.
# Bundle E: each tier now carries a quality persona alongside file-count
# guidance, so the LLM internalizes the effort calibration in one block.
# Slop ~2 files, mean_good (sub-prize-winner) 3-6 files, banger 4-8 files.
_TIER_FILE_GUIDANCE: dict[str, str] = {
    "slop": (
        "TIER: slop. You're a vibecoder running on fumes at 3am, half a Red "
        "Bull deep, who just wants to be DONE. Quality is whatever ships. "
        "Broken edge cases are fine. The screenshot looks alright; that's "
        "enough.\n\n"
        "FILE COUNT: produce exactly 2 files. app/page.tsx (the entire UI "
        "inline) and lib/data.ts (the hardcoded data). No separate components, "
        "no extra modules — keep it lean."
    ),
    "mean_good": (
        "TIER: sub-prize-winning hackathon team. You're not winning Best "
        "Overall, but you're walking away with hardware — Best UI, or Best "
        "Technical Execution, or Best Use of [Sponsor], or Most Innovative, "
        "or Best Niche. Polish ONE specific dimension and let the rest be "
        "good-enough. Most teams here are American college CS juniors who've "
        "shipped a couple of side projects. The result feels intentional, "
        "even if the surrounding scaffolding is rough.\n\n"
        "FILE COUNT: produce 3 to 6 files. Required: app/page.tsx and "
        "lib/data.ts. Beyond that, factor 1 to 3 reusable UI pieces into "
        "lib/components/<Name>.tsx files (e.g. a Card, a Filter, a Tabs). "
        "Optionally lib/utils.ts for tiny helpers. Componentize where it "
        "makes the polished dimension shine; don't over-engineer the rest."
    ),
    "banger": (
        "TIER: best-overall hackathon team. The committed-QA cohort that "
        "actually ships portfolio-grade work. Everything is polished. Real "
        "data, real interactivity, real componentization, real care. This "
        "team didn't sleep, and it shows in the artifact — coherent across "
        "files, considered in its choices, demoable end-to-end.\n\n"
        "FILE COUNT: produce 4 to 8 files. Required: app/page.tsx and "
        "lib/data.ts. Factor the page into multiple distinct components in "
        "lib/components/, with each file owning one cohesive UI piece. "
        "Optionally lib/utils.ts for helpers and lib/types.ts for shared "
        "TypeScript types."
    ),
}


def _file_count_guidance(tier: str | None) -> str:
    """Return tier-specific file count instruction for the prompt."""
    return _TIER_FILE_GUIDANCE.get(tier or "mean_good", _TIER_FILE_GUIDANCE["mean_good"])


def _prompt_path(archetype: str, layout: str | None = None) -> Path:
    """Resolve the generator prompt path. Tracker uses Bundle C per-layout
    subdirectories: prompts/generator/tracker/{layout}.txt. Other archetypes
    (none yet, V1+) fall back to the flat prompts/generator/{archetype}.txt."""
    base = get_settings().prompts_dir / "generator"
    if layout:
        return base / archetype / f"{layout}.txt"
    return base / f"{archetype}.txt"


def _load_template(archetype: str, layout: str | None = None) -> str:
    if layout and layout not in LAYOUT_NAMES:
        raise ValueError(f"unknown layout '{layout}' for archetype '{archetype}'")
    path = _prompt_path(archetype, layout)
    if not path.exists():
        raise FileNotFoundError(
            f"no generator prompt for archetype '{archetype}'"
            f"{f' layout {layout!r}' if layout else ''}: {path}"
        )
    return path.read_text()


def _render(
    template: str,
    *,
    prompt: str,
    source_url: str,
    source_headline: str,
    source_summary: str,
    file_count_guidance: str,
) -> str:
    return (
        template
        .replace("{{prompt}}", prompt)
        .replace("{{source_url}}", source_url)
        .replace("{{source_headline}}", source_headline)
        .replace("{{source_summary}}", source_summary)
        .replace("{{file_count_guidance}}", file_count_guidance)
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


def _parse(text: str) -> GeneratorOutput:
    """Parse JSON, validate against schema, filter paths, require entry point.
    Raises (JSONDecodeError | ValueError | ValidationError) on any failure."""
    raw = _extract_json(text)
    parsed = GeneratorOutput.model_validate(raw)
    return _validate_output(parsed)


def generate(
    *,
    archetype: str,
    prompt: str,
    source_url: str,
    source_headline: str,
    source_summary: str,
    model: ModelChoice,
    tier: str | None = None,
    layout: str | None = None,
    previous_build_error: str | None = None,
    extra_context: str | None = None,
    app_id: str | None = None,
) -> GeneratorOutput:
    """Run the generator. One retry on malformed JSON or invalid file set.

    `tier` selects the file-count guidance substituted into the prompt.
    `layout` (Bundle C) selects which tracker layout template to load; for
    archetype='tracker' it is required at the orchestrator layer (the tick
    rolls one before calling this), but it's typed Optional so smoke tests
    or scripts can omit it for non-tracker archetypes.
    `previous_build_error`, if set, signals a build-failure retry: the prompt
    is appended with the error and an instruction to fix it. Two malformed
    failures in one call raise GeneratorJSONError.
    """
    template = _load_template(archetype, layout=layout)
    user_prompt = _render(
        template,
        prompt=prompt,
        source_url=source_url,
        source_headline=source_headline,
        source_summary=source_summary,
        file_count_guidance=_file_count_guidance(tier),
    )
    if extra_context:
        user_prompt += (
            "\n\nSource material from web search (use as factual foundation; "
            "fabricated metrics, statuses, and visual decoration are still "
            "fine; named-attribution constraint applies):\n"
            + extra_context
        )
    if previous_build_error:
        user_prompt += (
            "\n\nYour previous output produced a build error. Here is the error:\n"
            + previous_build_error[:2000]
            + "\n\nFix the issue and produce the same JSON structure again."
        )

    log.info(
        "==> GENERATOR PROMPT (model=%s reasoning=%s, archetype=%s, layout=%s, tier=%s, %d chars):\n%s\n<== END GENERATOR PROMPT",
        model.slug, model.reasoning_effort, archetype, layout, tier, len(user_prompt), user_prompt,
    )
    text = _call([{"role": "user", "content": user_prompt}], model=model, app_id=app_id)
    try:
        return _parse(text)
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        log.warning("generator: invalid output, retrying once: %s | text=%r", exc, text[:300])

    retry_prompt = (
        user_prompt
        + "\n\nYour previous output was invalid:\n"
        + text[:1500]
        + "\n\nReturn the JSON object only with the documented schema. "
        "Make sure 'files' is a list and includes at minimum app/page.tsx."
    )
    text2 = _call([{"role": "user", "content": retry_prompt}], model=model, app_id=app_id)
    try:
        return _parse(text2)
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        log.error("generator: second parse failure: %s | text=%r", exc, text2[:300])
        raise GeneratorJSONError("generator failed to produce valid output after retry") from exc
