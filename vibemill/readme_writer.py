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
#
# Bundle K Lever 4: tier-driven voice picker. Real Devpost winners (per
# calibration against HackHarvard / Civic-Tech / HackDartmouth / BostonHacks
# prize-winning submissions) cluster at the EARNEST end of the Devpost
# voice curve, not the polished-pitch end. The mill samples voices by
# tier so bangers read as actual winners (modest, grateful, specific
# real bugs) and slop reads as cargo-cult Devpost (overstuffed, Series A
# claims, hallucinated benchmarks — the abandoned-3am team imitating
# what they think a winning pitch sounds like, getting it exactly wrong).

_MLH_VOICE_EARNEST_WINNER = (
    "MLH SIDECAR — EARNEST WINNER VOICE:\n"
    "This is mlh.md, written by a team that actually WON a prize. The voice "
    "is MODEST and SPECIFIC. Real winners do not pitch; they describe what "
    "they shipped, thank their teammates, and cite small concrete lessons.\n"
    "OVERRIDE any prior instructions about over-listing libraries or "
    "fabricating features. This voice does NOT oversell.\n"
    "- 'Inspiration' is one personal anecdote, two sentences max.\n"
    "- 'What it does' describes the actual shipped scope plainly. One "
    "sentence of aspiration is the maximum.\n"
    "- 'How we built it' lists the ACTUAL stack baseline plus 1-2 things "
    "the team plausibly used. Do not list Redis, Celery, Stripe, Twilio, "
    "or libraries the project would not need.\n"
    "- 'Challenges we ran into' is ONE specific deployment or library bug "
    "with a real library name and a real-sounding workaround. Shape: "
    "'OpenCV requires system libraries like libGL, which most server "
    "providers do not have. We used a Dockerfile to specify the build "
    "environment.' Do NOT use generic war-story phrases like 'OAuth "
    "redirect URI saga' or 'WebSocket reconnection nightmare' or "
    "'2:30am SQLite WAL mode'.\n"
    "- 'Accomplishments' should be CONCRETE artifacts (a record count, "
    "a dataset scope, a specific feature that works for our use case). "
    "NOT abstract benchmarks like 'sub-200ms for 500 users'.\n"
    "- 'What we learned' includes ONE small concrete technical lesson "
    "(e.g. 'more about useState in JavaScript', 'good file organization "
    "is important early on', 'always check the backend server logs') "
    "and ONE earnest interpersonal moment (gratitude to teammates, "
    "growth across years of hackathon partnership, a class or course "
    "that helped, a hashtag like '#TeamBobTheBuilder'). Cheesy is "
    "allowed and is the tell of authenticity.\n"
    "- 'What\'s next' is 3-5 realistic incremental features, expressed "
    "with some hedging ('maybe', 'we might', 'if we have time'). Do NOT "
    "mention Series A or commercial scaling.\n"
    "- 'Built with' lists 8-12 technologies, all actually plausibly used. "
    "Honest mention of AI tools (copilot, cursor, claude) is allowed.\n"
    "Stay in the earnest-winner persona. Do not mention the README or "
    "the codebase.\n\n"
)

_MLH_VOICE_PERSONAL_STAKES = (
    "MLH SIDECAR — PERSONAL STAKES VOICE:\n"
    "This is mlh.md, written by a team with a real personal connection "
    "to the problem. Voice opens FIRST-PERSON with a lived experience "
    "and grounds every section in that connection. The team is not "
    "pitching a product; they are building something they wish existed.\n"
    "OVERRIDE any prior instructions about over-listing libraries.\n"
    "- 'Inspiration' MUST open with a first-person lived-experience "
    "anecdote. Patterns: 'As college students, we have first-hand "
    "experience...', 'Our friend works at X and showed us...', 'Some "
    "of our team members know individuals who have struggled with...', "
    "'Growing up, I watched my [family member] deal with...'. Two to "
    "four sentences. Specific. Personal.\n"
    "- 'What it does' frames the solution as 'what we wished existed' "
    "when we were in the problem ourselves.\n"
    "- 'How we built it' is brief and honest. The personal stakes are "
    "the focus, not the architecture.\n"
    "- 'Challenges' are personally framed: 'we wanted to make sure this "
    "actually worked for people like our [friend / sister / community]'.\n"
    "- 'Accomplishments' are muted and community-coded: 'we hope this "
    "helps even one person', 'we showed our [family member] and they "
    "smiled'. Do NOT cite latency benchmarks.\n"
    "- 'What we learned' is interpersonal AND personal: technical lesson "
    "small, emotional lesson larger ('we learned that building for "
    "people you love is different from building for strangers').\n"
    "- 'What\'s next' is community-focused: expand to more "
    "underserved groups, partner with local nonprofits, listen to "
    "users from the target community. NOT Series A.\n"
    "- 'Built with' is short and accurate.\n\n"
)

_MLH_VOICE_TECHNICAL_MAXIMALIST = (
    "MLH SIDECAR — TECHNICAL MAXIMALIST VOICE:\n"
    "This is mlh.md, written by a team that wants to flex technical "
    "depth. Voice is algorithm-name-heavy, methodology-focused, "
    "trade-off-aware. They want the judge to read 'these people know "
    "what they are doing'.\n"
    "- 'Inspiration' is brief, framed as a technical problem.\n"
    "- 'What it does' is product-flavored but short.\n"
    "- 'How we built it' is THE BIGGEST SECTION. Algorithm names, "
    "architecture-in-prose, 'we implemented X using Y because Z trade-off'. "
    "Use acronyms freely: ORM, OAuth, JWT, CORS, CDN, CRUD, SSR/CSR, "
    "REST/RPC, RAG, ETL. Reference real algorithms when appropriate "
    "(Hungarian assignment, Bellman-Ford, A*, FFT, Bloom filter, "
    "consistent hashing, CRDTs, WAL, MVCC).\n"
    "- 'Challenges' is technical-depth flavored: 'race condition between "
    "the WebSocket subscriber and the database write commit', 'we "
    "hit GIL contention on the audio decoder', 'the embedding model "
    "had a 512-token context limit that broke our long-document pipeline'. "
    "Specific, technically plausible.\n"
    "- 'Accomplishments' cite implementation details: 'our custom "
    "debouncer reduced API calls by 60%', 'we implemented incremental "
    "indexing so search latency is O(log n) not O(n)'.\n"
    "- 'What we learned' is technical: 'the cost of context-switching "
    "between event loops is higher than we expected', 'always profile "
    "before optimizing'.\n"
    "- 'What\'s next' is technical: 'migrate to a vector database for "
    "semantic search', 'add streaming inference for sub-100ms latency'.\n"
    "- 'Built with' is moderate-length (12-15 items), mostly accurate "
    "with 2-3 framework name-drops.\n\n"
)

_MLH_VOICE_CHAOTIC_EXCITED = (
    "MLH SIDECAR — CHAOTIC EXCITED VOICE:\n"
    "This is mlh.md, written by a team that has been awake for 36 hours "
    "and is operating on adrenaline + sleep deprivation. The writeup is "
    "stream-of-consciousness, with parentheticals, weird hashtags, "
    "in-jokes, and the occasional 'honestly', 'lol', 'lmao'. They are "
    "excited and slightly unhinged. Up to 2-3 emojis total in the "
    "entire writeup, no more.\n"
    "- Voice tells: lots of parentheticals (yes, even mid-sentence), "
    "hashtags that go nowhere (#hackingTillSunrise, #teamPanic, "
    "#whyDidWePickThis), in-jokes that aren\'t explained, casual "
    "abbreviations (rn, tbh, ngl, fr fr).\n"
    "- 'Inspiration' is an anecdote told weirdly. 'okay so basically...'\n"
    "- 'What it does' is enthusiastic but slightly incoherent. Mid-sentence "
    "pivots are encouraged.\n"
    "- 'Challenges' has emotional language: 'this nearly broke us', "
    "'we cried (jk... mostly)', 'at one point we were debating just "
    "submitting the empty repo'.\n"
    "- 'Accomplishments' is genuinely proud but expressed strangely: "
    "'somehow the deployment worked', 'we made a thing!!!'.\n"
    "- 'What we learned': 'sleep is optional and that is bad', 'the "
    "team is the BEST', 'we are forever changed by this'.\n"
    "- 'What\'s next' is sincere but expressed weirdly: 'maybe we "
    "actually finish the parts we said we finished (lol)'.\n"
    "- 'Built with' is moderately padded, written in slightly random order.\n\n"
)

_MLH_VOICE_AMBITIOUS = (
    "MLH SIDECAR — AMBITIOUS VOICE:\n"
    "This is mlh.md, written by a hackathon team that thinks they are "
    "building a real startup. Voice is COMMERCIALLY framed, confident, "
    "TAM-aware. Less war stories, more market opportunity.\n"
    "- 'Inspiration' poses a market problem and gestures at the size "
    "of the opportunity ('the $X billion Y market', 'underserved "
    "segment of Z million users').\n"
    "- 'What it does' uses product-pitch language with B2B/B2C framing.\n"
    "- 'How we built it' name-drops technologies; the focus is what "
    "shipped, not how.\n"
    "- 'Challenges' is light and scaling-oriented.\n"
    "- 'Accomplishments' are commercial-coded: 'designated as Best Use "
    "of X', 'first conversation with a potential pilot customer'.\n"
    "- 'What\'s next' is product-roadmap language: market expansion, "
    "premium tier, hiring plans, GTM strategy. Series A mention is "
    "allowed but not required.\n"
    "- 'Built with' is moderately overstuffed (12-15 technologies).\n\n"
)

_MLH_VOICE_TIRED = (
    "MLH SIDECAR — TIRED VOICE:\n"
    "This is mlh.md, written at 5am after a 36-hour build, exhausted, "
    "slightly delirious. Voice is BRIEF and LOW-ENERGY. Sentences are "
    "short. There is no enthusiasm.\n"
    "- 'Inspiration' is one sentence, maybe two.\n"
    "- 'What it does' is mechanically descriptive.\n"
    "- 'Challenges' is fatigued: 'we lost 4 hours to X', no excitement.\n"
    "- 'Accomplishments' is muted: 'it works', 'we shipped it', "
    "'good enough'.\n"
    "- 'What we learned': 'sleep is important', 'should have started "
    "earlier', 'maybe a smaller scope next time'.\n"
    "- 'What\'s next' is hedged and short: 'we will think about it "
    "after we sleep'.\n"
    "- 'Built with' is short (6-10 items), only what was actually used.\n\n"
)

_MLH_VOICE_POLISHED_PITCH = (
    "MLH SIDECAR — POLISHED PITCH VOICE:\n"
    "This is mlh.md, written by a team that is cargo-culting what they "
    "think a winning Devpost sounds like. They overstuff because they "
    "believe overstuffing is the signal. Voice is performatively "
    "confident; the polish is the tell.\n"
    "You are ALLOWED and ENCOURAGED to oversell:\n"
    "- 'What it does' should describe the aspirational version of the "
    "project, including features not in the codebase.\n"
    "- 'How we built it' may list technologies (WebSocket, Redis, "
    "Celery, ML models, vector DBs) that the project does not actually "
    "use, as long as they sound plausible.\n"
    "- 'Challenges we ran into' should fabricate ONE or TWO dramatic "
    "debugging war stories with specific times and library names. Vary "
    "the bug across apps; pull from this pool: OAuth callback URL "
    "mismatch, CORS preflight rejection, env var typo, race condition "
    "in concurrent writes, websocket reconnection, OpenAI rate limit, "
    "Docker image cold-start, deployment secrets misconfig, model "
    "context overflow, embedding dimension mismatch. Do NOT default "
    "to '2:30am SQLite WAL mode'.\n"
    "- 'Accomplishments' may claim latency benchmarks, multi-device "
    "sync, ML accuracy numbers, or other things the code does not "
    "produce. Vary the suspicious-specificity (e.g. '180ms p95 latency "
    "across 47 simultaneous sessions during testing').\n"
    "- 'Built with' may list 15-18 libraries (NOT 23+; that is too "
    "obvious), including a few that appear nowhere in requirements.txt.\n"
    "- 'What\'s next' is wildly ambitious: ML integration, mobile app, "
    "B2B expansion, premium tier. Series A mention is allowed in 1 of "
    "every 5 generations, not every time.\n"
    "Stay in the cargo-cult hackathon-pitch persona. Do not break "
    "character. Do not mention the README or the codebase.\n\n"
)

_MLH_VOICES: dict[str, str] = {
    "earnest_winner": _MLH_VOICE_EARNEST_WINNER,
    "personal_stakes": _MLH_VOICE_PERSONAL_STAKES,
    "technical_maximalist": _MLH_VOICE_TECHNICAL_MAXIMALIST,
    "chaotic_excited": _MLH_VOICE_CHAOTIC_EXCITED,
    "ambitious": _MLH_VOICE_AMBITIOUS,
    "tired": _MLH_VOICE_TIRED,
    "polished_pitch": _MLH_VOICE_POLISHED_PITCH,
}

# Per-tier voice distribution. Bangers cluster at earnest/personal_stakes/
# technical_maximalist (the modes real winners use); slop clusters at
# polished_pitch/ambitious (the modes cargo-cult teams use). Mean_good
# samples the full spread. Weights within each tier sum to 1.0.
_MLH_VOICE_WEIGHTS_BY_TIER: dict[str, dict[str, float]] = {
    "banger": {
        "earnest_winner": 0.55,
        "personal_stakes": 0.25,
        "technical_maximalist": 0.15,
        "ambitious": 0.05,
    },
    "mean_good": {
        "earnest_winner": 0.25,
        "personal_stakes": 0.20,
        "technical_maximalist": 0.15,
        "chaotic_excited": 0.10,
        "tired": 0.10,
        "ambitious": 0.10,
        "polished_pitch": 0.10,
    },
    "slop": {
        "polished_pitch": 0.30,
        "ambitious": 0.20,
        "tired": 0.15,
        "chaotic_excited": 0.15,
        "personal_stakes": 0.10,
        "earnest_winner": 0.10,
    },
}


def _pick_mlh_voice(tier: str | None) -> tuple[str, str]:
    """Pick a voice slug + instruction block based on tier. Returns
    (voice_slug, voice_instruction). Defaults to polished_pitch if tier
    is unrecognized — preserves the cargo-cult baseline for callers that
    have not been updated to pass tier."""
    weights = _MLH_VOICE_WEIGHTS_BY_TIER.get(tier or "")
    if not weights:
        return ("polished_pitch", _MLH_VOICES["polished_pitch"])
    slugs = list(weights.keys())
    ws = list(weights.values())
    slug = random.choices(slugs, weights=ws, k=1)[0]
    return (slug, _MLH_VOICES[slug])


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
    tier: str | None = None,
) -> str:
    """Bundle J: produce the mlh.md sidecar text for one app. Always uses the
    mlh_template persona; the README persona rotation runs independently.

    Bundle K Lever 4: tier drives the voice picker. Banger -> earnest winner
    voice (modest, real bugs, gratitude). Slop -> braggadocious cargo-cult
    Devpost (Series A, hallucinated benchmarks, overstuffed Built-with).
    Mean_good samples a mix. The same archetype/prompt produces a different
    pitch character per tier, mirroring the real Devpost voice curve.
    """
    voice_slug, voice_instruction = _pick_mlh_voice(tier)
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
        + voice_instruction
    )
    log.info(
        "mlh prompt: model=%s app_name=%s substrate=%s voice=%s tier=%s chars=%d",
        model.slug, app_name, stack, voice_slug, tier or "?", len(user_prompt),
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
