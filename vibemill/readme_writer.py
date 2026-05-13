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
_GRADIO_SUBSTRATE_PREFACE = (
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

# Bundle I: Flask + github_only. The app lives as a GitHub repo with no
# live deploy; the README must include real, runnable setup steps that
# walk the reader through cloning, installing, configuring secrets, and
# running locally. Some steps may be partially-broken (on-brand), but
# the README must NOT lie about features the code lacks.
_FLASK_SUBSTRATE_PREFACE = (
    "SUBSTRATE OVERRIDE (Bundle I):\n"
    "This app is a Python Flask app that lives as a GitHub repo only - "
    "no Vercel, no HF Spaces, NOT a Next.js app. Adapt the README:\n"
    "- Tech stack: Python, Flask, Jinja templates, plus whichever DB / "
    "auth libraries the app uses (sqlite3, SQLAlchemy, Flask-Login, "
    "authlib, etc.). Do NOT mention Next.js, TypeScript, Tailwind, React, "
    "or npm.\n"
    "- Include a complete, runnable SETUP section: clone, python -m venv, "
    "source activate, pip install -r requirements.txt, copy .env.example "
    "to .env and fill in placeholders, any DB-init steps (e.g. "
    "`flask db upgrade` or `python -c \"from app import db; db.create_all()\"`), "
    "then `flask run` or `python app.py`.\n"
    "- If the app uses Google OAuth or similar: include the steps to "
    "create a Google Cloud project, enable the relevant APIs, generate "
    "OAuth 2.0 credentials, and paste client_id + client_secret into "
    ".env. Hackathon-authentic step-count is fine (5-10 steps).\n"
    "- If the app uses a Postgres or Mongo container: include a "
    "`docker-compose up -d` step before the migrations.\n"
    "- Hackathon-cliche details encouraged: 'Tested on macOS Sonoma + "
    "Python 3.11', 'YMMV on Windows', 'Note: the OAuth flow doesn't "
    "work in incognito mode for some reason, idk.'\n"
    "- The README must NOT claim features the code doesn't actually "
    "include. Steps that don't work because of code bugs are on-brand; "
    "boasting about features that aren't in the codebase is not.\n"
    "- DO NOT mention deployment to Heroku, Vercel, Railway, etc. This "
    "is intentionally a clone-and-run project.\n\n"
)

# Operational honesty disclosure prepended to every README. CLAUDE.md
# requires every generated app to disclose that it is machine-produced.
# The footer disclosure was the original surface; this README-top blockquote
# makes the same statement more prominent for anyone landing on the GitHub
# repo. Worded per ANTI_PATTERNS rule 7: no "satire" label in user-facing
# copy; the framing lives at vibemill.dev, not in the artifact itself.
VIBEMILL_DISCLAIMER = (
    "> Generated by [Vibe Mill](https://vibemill.dev). "
    "This repository was produced by an automated pipeline. "
    "No human wrote this code. "
    "It is not a product and should not be treated as one."
)


# (persona_name, weight). Weights must sum to 1.0.
# Bundle E rebalanced and added 5 new personas (12 total). The new five
# are founder_hustle, academic, shitpost, mlh_template, and grindset.
# Bundle J: mlh_template is pulled from the README rotation and ships
# instead as a mandatory `mlh.md` sidecar on every repo (Devpost-format
# pitch doc that runs in parallel with the README). Its 0.07 weight is
# absorbed into enthusiastic (closest in voice).
README_PERSONAS: tuple[tuple[str, float], ...] = (
    ("enthusiastic", 0.32),
    ("minimalist", 0.15),
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

# Bundle J: the mlh.md sidecar always uses this template, regardless of
# whichever persona was rolled for README.md.
MLH_SIDECAR_PERSONA: str = "mlh_template"

VALID_PERSONAS: frozenset[str] = frozenset(
    [name for name, _ in README_PERSONAS] + [MLH_SIDECAR_PERSONA]
)


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


# Bundle J: oversell preface injected for the mlh.md sidecar only. The
# README.md path still gets the substrate prefaces above (which include
# "must not claim features the code doesn't include" for Flask). The
# mlh.md path explicitly overrides that rule. Disclaimer + machine-output
# transparency carry the operational honesty; the mlh.md gets to perform
# the genre fully.
_MLH_OVERSELL_PREFACE = (
    "MLH SIDECAR OVERRIDE:\n"
    "This is mlh.md, a Devpost-style pitch that ships alongside README.md "
    "in the same repo. The README is the honest technical doc. THIS file "
    "is the hackathon-team pitch persona on submission day at 5am, deeply "
    "tired and deeply confident, trying to bluff their way to Best Overall. "
    "You are EXPLICITLY ALLOWED and ENCOURAGED to oversell:\n"
    "- 'What it does' should describe the aspirational version of the "
    "project, including features that are not in the codebase.\n"
    "- 'How we built it' may list technologies (WebSocket, Redis, Celery, "
    "ML models, real-time pipelines, vector DBs) that the project does not "
    "actually use, as long as they sound plausible for the project type.\n"
    "- 'Challenges we ran into' should fabricate specific, dramatic "
    "debugging war stories: WebSocket reconnection nightmares, OAuth "
    "redirect URI saga, '2:30am SQLite WAL mode fix', '6 hours lost to "
    "speaker diarization', specific times and library names. Concrete > vague.\n"
    "- 'Accomplishments' may claim latency benchmarks, multi-device sync, "
    "ML accuracy numbers, deployment milestones, or other things the code "
    "does not actually produce.\n"
    "- 'Built with' may list libraries that appear nowhere in "
    "requirements.txt or package.json - the more libraries the better.\n"
    "- 'What's next' should be wildly ambitious: ML integration, mobile "
    "app, Series A, etc.\n"
    "Stay in the hackathon-team persona. Do not break the fourth wall. "
    "Do not mention the README, the codebase, or the discrepancy.\n\n"
)


def _mlh_substrate_hint(stack: str) -> str:
    """Stack baseline + an invitation to overlist relatable hackathon tech in
    'Built with', regardless of whether the code uses any of it."""
    if stack == "gradio":
        return (
            "Stack baseline for this app: Python, Gradio, Hugging Face Spaces. "
            "'Built with' may also list: PyTorch, Transformers, OpenAI, "
            "Anthropic, LangChain, ChromaDB, Pinecone, FAISS, Whisper, "
            "pyannote-audio, etc. (regardless of whether the code imports them).\n\n"
        )
    if stack == "flask":
        return (
            "Stack baseline for this app: Python, Flask, Jinja, SQLAlchemy "
            "or SQLite, optional Flask-Login / Authlib. 'Built with' may "
            "also list: Redis, Celery, WebSockets / Flask-SocketIO, Docker, "
            "PostgreSQL, AWS S3, Stripe, Twilio, OpenAI, etc. (regardless of "
            "whether the code imports them).\n\n"
        )
    return (
        "Stack baseline for this app: Next.js, TypeScript, Tailwind, Vercel. "
        "'Built with' may also list: tRPC, Prisma, PostgreSQL, Supabase, "
        "Clerk / Auth0, Stripe, OpenAI, Vercel AI SDK, Redis, etc. "
        "(regardless of whether the code imports them).\n\n"
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
    # Bundle H/I: append the substrate override so the LLM swaps Next.js/npm
    # specifics for the right stack. Persona voice and section structure
    # are still followed.
    stack = SUBSTRATE_BY_ARCHETYPE.get(archetype, "nextjs")
    if stack == "gradio":
        user_prompt = user_prompt + "\n\n" + _GRADIO_SUBSTRATE_PREFACE
    elif stack == "flask":
        user_prompt = user_prompt + "\n\n" + _FLASK_SUBSTRATE_PREFACE
    log.info(
        "readme prompt: model=%s persona=%s app_name=%s substrate=%s chars=%d",
        model.slug, persona, app_name, stack, len(user_prompt),
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
        log.warning("readme_writer: empty output; shipping disclaimer-only README")
        return VIBEMILL_DISCLAIMER
    return f"{VIBEMILL_DISCLAIMER}\n\n{text}"


def write_mlh(
    *,
    app_name: str,
    prompt: str,
    archetype: str,
    model: ModelChoice,
    source_headline: str = "",
    app_id: str | None = None,
) -> str:
    """Bundle J: produce the mlh.md sidecar text for one app. Always uses the
    mlh_template persona; the README persona rotation runs independently.

    Unlike README.md, the mlh.md is explicitly allowed to oversell - fabricate
    challenges, list libraries the code never imports, claim accomplishments
    that don't exist. The disclaimer at the top of every artifact carries the
    operational honesty; this file gets to perform the genre fully.
    """
    user_prompt = _render(
        _load_template(MLH_SIDECAR_PERSONA),
        app_name=app_name,
        prompt=prompt,
        archetype=archetype,
        source_headline=source_headline,
    )
    stack = SUBSTRATE_BY_ARCHETYPE.get(archetype, "nextjs")
    user_prompt = (
        user_prompt
        + "\n\n"
        + _mlh_substrate_hint(stack)
        + _MLH_OVERSELL_PREFACE
    )
    log.info(
        "mlh prompt: model=%s app_name=%s substrate=%s chars=%d",
        model.slug, app_name, stack, len(user_prompt),
    )
    completion = openrouter.complete(
        model=model.slug,
        messages=[{"role": "user", "content": user_prompt}],
        purpose="mlh",
        temperature=0.8,  # slightly hotter than README; we want fabrication variance
        reasoning_effort=model.reasoning_effort,
        app_id=app_id,
        max_tokens=2000,
    )
    text = (completion.text or "").strip()
    if not text:
        log.warning("readme_writer: empty mlh output; shipping disclaimer-only mlh.md")
        return VIBEMILL_DISCLAIMER
    return f"{VIBEMILL_DISCLAIMER}\n\n{text}"
