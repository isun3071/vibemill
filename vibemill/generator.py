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
- Path validation: substrate-dependent (Bundle H). JS archetypes accept
  app/* and lib/* with .ts/.tsx/.css. Python archetypes accept top-level
  .py files plus requirements.txt.
- Chassis-owned paths are silently dropped if the LLM tries to write them.
  JS: app/layout.tsx + app/globals.css. Python: README.md + .gitignore.
- A substrate-specific required entry point must be present in the
  validated set. JS: app/page.tsx. Python: app.py. Without it the build
  has no entry point; we surface this as a JSON error to trigger retry.

Bundle H: Python archetypes (ai_generator, ai_agent) route through this
generator the same way; substrate dispatch happens in _rules_for() via
models.SUBSTRATE_BY_ARCHETYPE.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .clients import openrouter
from .config import get_settings
from .layouts import LAYOUT_NAMES
from .model_rotation import ModelChoice
from .models import SUBSTRATE_BY_ARCHETYPE, GeneratedFile, GeneratorOutput

log = logging.getLogger(__name__)

GENERATOR_TEMPERATURE = 0.7  # see ANTI_PATTERNS.md rule 4
_MAX_TOKENS = 12000  # raised from 8k for multi-file output


@dataclass(frozen=True)
class SubstrateRules:
    """Per-substrate file-path policy. The generator dispatches by archetype
    to either JS_RULES (Next.js apps) or PYTHON_RULES (Gradio apps)."""
    required_path: str
    allowed_path_prefixes: tuple[str, ...]   # empty = top-level only
    allowed_extensions: tuple[str, ...]
    allowed_basenames: frozenset[str]        # explicit allowlist (e.g. requirements.txt)
    chassis_owned: frozenset[str]


JS_RULES = SubstrateRules(
    required_path="app/page.tsx",
    allowed_path_prefixes=("app/", "lib/"),
    allowed_extensions=(".ts", ".tsx", ".css"),
    allowed_basenames=frozenset(),
    # layout.tsx carries the Vibe Mill footer (ANTI_PATTERNS rule 10),
    # and globals.css holds the Tailwind directives.
    chassis_owned=frozenset({"app/layout.tsx", "app/globals.css"}),
)

# Bundle H: Gradio apps on HF Spaces. Top-level .py files only; the
# chassis README has HF Spaces YAML frontmatter pinning python_version,
# sdk_version, app_file.
GRADIO_RULES = SubstrateRules(
    required_path="app.py",
    allowed_path_prefixes=(),
    allowed_extensions=(".py",),
    allowed_basenames=frozenset({"requirements.txt"}),
    chassis_owned=frozenset({"README.md", ".gitignore"}),
)

# Bundle I: Flask apps that live as GitHub repos (deploy_target=github_only).
# Allowed structure: app.py, templates/*.html, static/{css,js,...}, optional
# top-level helper .py files. README.md is LLM-produced (no HF frontmatter),
# .gitignore is chassis-owned, .env.example is LLM-produced (placeholder
# values for OAuth client_id/client_secret, DB URLs, etc.).
FLASK_RULES = SubstrateRules(
    required_path="app.py",
    allowed_path_prefixes=("templates/", "static/"),
    allowed_extensions=(".py", ".html", ".css", ".js"),
    allowed_basenames=frozenset({
        "requirements.txt", ".env.example", "Dockerfile", "docker-compose.yml",
    }),
    # .gitignore is chassis-pinned (Python ignore patterns); the LLM
    # produces README.md (the persona-driven setup-steps narrative).
    chassis_owned=frozenset({".gitignore"}),
)

# Back-compat alias. Pre-Bundle-I code referenced PYTHON_RULES when it
# meant "Gradio rules." Keep the alias so external references don't break.
PYTHON_RULES = GRADIO_RULES


def _rules_for(archetype: str) -> SubstrateRules:
    stack = SUBSTRATE_BY_ARCHETYPE.get(archetype, "nextjs")
    if stack == "gradio":
        return GRADIO_RULES
    if stack == "flask":
        return FLASK_RULES
    return JS_RULES


class GeneratorJSONError(RuntimeError):
    """Both generator attempts produced unparseable JSON or invalid output."""


def _is_valid_slot_path(path: str, rules: SubstrateRules) -> tuple[bool, str | None]:
    """(ok, reason_if_not). Strict path validation against the substrate rules."""
    if not path or path.startswith("/") or "\\" in path:
        return False, "path must be relative, no backslashes"
    parts = path.split("/")
    if ".." in parts:
        return False, "path traversal not allowed"
    # Explicit basename allowlist (e.g. requirements.txt) bypasses
    # prefix/extension checks.
    basename = parts[-1]
    if basename in rules.allowed_basenames and len(parts) == 1:
        return True, None
    if rules.allowed_path_prefixes:
        if not any(path.startswith(p) for p in rules.allowed_path_prefixes):
            return False, f"path must start with {rules.allowed_path_prefixes} or be one of {sorted(rules.allowed_basenames)}"
    else:
        # No prefixes allowed: must be top-level.
        if len(parts) != 1:
            return False, "path must be top-level (no subdirectories)"
    if not any(path.endswith(e) for e in rules.allowed_extensions):
        return False, f"file extension must be one of {rules.allowed_extensions}"
    return True, None


def _filter_files(files: list[GeneratedFile], rules: SubstrateRules) -> list[GeneratedFile]:
    """Drop chassis-owned and invalid paths. Last-write-wins for duplicates.
    Logs every drop with a reason so the operator can see what the LLM tried."""
    by_path: dict[str, GeneratedFile] = {}
    for f in files:
        if f.path in rules.chassis_owned:
            log.warning("dropping LLM file %s: chassis owns this path", f.path)
            continue
        ok, reason = _is_valid_slot_path(f.path, rules)
        if not ok:
            log.warning("dropping LLM file %s: %s", f.path, reason)
            continue
        if f.path in by_path:
            log.info("duplicate path %s in LLM output; using last", f.path)
        by_path[f.path] = f
    return list(by_path.values())


def _validate_output(out: GeneratorOutput, rules: SubstrateRules) -> GeneratorOutput:
    """Filter out invalid/chassis-owned files; require the substrate's entry
    point. Returns a sanitized GeneratorOutput; raises ValueError if the
    required entry-point file is missing after filtering."""
    valid = _filter_files(out.files, rules)
    if not any(f.path == rules.required_path for f in valid):
        raise ValueError(f"output missing required {rules.required_path}")
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
        "ships MVP-form output: polished across multiple dimensions, "
        "demoable end-to-end, pitch-deck-with-repo shaped. This is the "
        "artifact someone would actually show off at Demo Day. Real data, "
        "real interactivity, real componentization, real care. This team "
        "didn't sleep, and it shows — coherent across files, considered "
        "in its choices, the kind of project that wins Best Overall.\n\n"
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


def _parse(text: str, rules: SubstrateRules) -> GeneratorOutput:
    """Parse JSON, validate against schema, filter paths, require entry point.
    Raises (JSONDecodeError | ValueError | ValidationError) on any failure."""
    raw = _extract_json(text)
    parsed = GeneratorOutput.model_validate(raw)
    return _validate_output(parsed, rules)


def validate_output(out: GeneratorOutput, archetype: str) -> GeneratorOutput:
    """Public wrapper: validate against the rules for `archetype`. Used by
    verify.py to defensively re-validate the verifier's file list."""
    return _validate_output(out, _rules_for(archetype))


_BLEND_CONTEXT_TEMPLATE = (
    "\n\nBLEND CONTEXT (Bundle G — 2-archetype blend):\n"
    "The matcher rolled a blend: this app's PRIMARY archetype is "
    "{primary}, but the secondary archetype {secondary} also scored at "
    "or near the top. Weave a {secondary}-flavored sub-feature into the "
    "primary {primary} app so that someone looking at the final artifact "
    "could plausibly call it either form. Examples of natural blends: a "
    "chatbot that also recommends things (chatbot + recommendation_engine), "
    "a tracker with an inline AI chat panel (tracker + chatbot), a search "
    "directory with a per-item utility tool (search_directory + "
    "utility_tool). Pick a natural composition; don't force two whole "
    "apps into one page. The primary's structure dominates; the secondary "
    "appears as a section, panel, or sub-feature.\n"
)


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
    blend_partner: str | None = None,
    previous_build_error: str | None = None,
    extra_context: str | None = None,
    app_id: str | None = None,
) -> GeneratorOutput:
    """Run the generator. One retry on malformed JSON or invalid file set.

    `tier` selects the file-count guidance substituted into the prompt.
    `layout` (Bundle C) selects which tracker layout template to load.
    `blend_partner` (Bundle G), if set, names a secondary archetype to
    blend into the primary. Adds a BLEND CONTEXT preamble after the
    main template render. The LLM is asked to weave the secondary form
    in as a sub-feature; the primary's structure dominates.
    `previous_build_error`, if set, signals a build-failure retry: the
    prompt is appended with the error and an instruction to fix it. Two
    malformed failures in one call raise GeneratorJSONError.
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
    if blend_partner:
        user_prompt += _BLEND_CONTEXT_TEMPLATE.format(
            primary=archetype, secondary=blend_partner,
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

    rules = _rules_for(archetype)
    log.info(
        "generator prompt: model=%s reasoning=%s archetype=%s substrate=%s layout=%s tier=%s blend=%s chars=%d",
        model.slug, model.reasoning_effort, archetype,
        SUBSTRATE_BY_ARCHETYPE.get(archetype, "nextjs"),
        layout, tier, blend_partner, len(user_prompt),
    )
    text = _call([{"role": "user", "content": user_prompt}], model=model, app_id=app_id)
    try:
        return _parse(text, rules)
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        log.warning("generator: invalid output, retrying once: %s | text=%r", exc, text[:300])

    retry_prompt = (
        user_prompt
        + "\n\nYour previous output was invalid:\n"
        + text[:1500]
        + "\n\nReturn the JSON object only with the documented schema. "
        f"Make sure 'files' is a list and includes at minimum {rules.required_path}."
    )
    text2 = _call([{"role": "user", "content": retry_prompt}], model=model, app_id=app_id)
    try:
        return _parse(text2, rules)
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        log.error("generator: second parse failure: %s | text=%r", exc, text2[:300])
        raise GeneratorJSONError("generator failed to produce valid output after retry") from exc
