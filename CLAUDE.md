# Vibe Mill

> **Changelog v2:** Added the verification pass to V0 scope. Added ANTI_PATTERNS.md and THESIS.md to the document map. ANTI_PATTERNS.md is required reading; THESIS.md is recommended for understanding project intent.

> "There's a new kind of coding I call 'vibe coding', where you fully give in to the vibes, embrace exponentials, and forget that the code even exists."
> — Andrej Karpathy, February 2, 2025

Vibe Mill is a satirical app machine. It produces vibe-coded web applications from news headlines and one-line user prompts on a slow cadence (5–10 per day). The mill does not promise quality. The mill does not promise relevance. The mill ships.

This document is the operating manual for any AI assistant (Claude Code, Cursor, etc.) working on this codebase.

## What this project is

Vibe Mill is the industrialization of vibe coding as critique. Every app it produces is a counter-example to the resume bullet "shipped MVP using AI tools." The artifacts make the argument; we do not write a manifesto.

For the deeper intellectual framing, read `THESIS.md`. For the operational rules of *what not to improve*, read `ANTI_PATTERNS.md`. The first explains why the project exists; the second explains why "improvements" that look obvious are usually wrong.

The satire is bounded. The mill operates honestly:

- Every generated app discloses, in its footer, that it was machine-produced
- The mill does not pretend its output is human craft
- The mill respects content safety (inherits guard-model refusals)
- The mill does not spam (one email per ship, real unsubscribe)

## What this project is not

Vibe Mill is **not** a productivity tool, an AI startup, an engineering exercise in agentic AI, a vibe-coding platform for users, a tracker aggregator, a news service, or a portfolio piece intended to look impressive.

If a design decision starts to push toward any of those, push back.

## Critical: read ANTI_PATTERNS.md before improving anything

This codebase contains design choices that *look* like bugs or code smells but are intentional. Hallucination, overconfidence, shallow self-verification, and deliberately mid-quality outputs are load-bearing for the satire.

**Before improving any LLM call, prompt, or output, read `ANTI_PATTERNS.md`.** That document specifies what must not be improved and why. Drift toward "make it better" is the most predictable failure mode for any contributor to this project.

## V0 scope (what to build first)

Implement only the following in v0:

- **Orchestrator** at `/home/ian/vibemill/` on sunfamily, run hourly via systemd timer
- **News ingestion** from AP and BBC RSS feeds
- **Guard model pass** (claude haiku via OpenRouter, t=0) for content safety; rejects inherit LLM refusal
- **Matcher** (claude haiku via OpenRouter, t=0) scoring against the **Tracker** archetype only; threshold 7
- **Code generator** (DeepSeek V3 via OpenRouter, t=0.7) producing Tracker apps
- **Verification pass** (DeepSeek V3 via OpenRouter, t=0.3, one-sentence prompt) — informational, not gating
- **Readme writer** (claude haiku via OpenRouter) producing vibecoder-persona READMEs
- **GitHub publisher** creating repos in the `vibemill-apps` org with fake commit history
- **Vercel deployer** auto-deploying via the Vercel API
- **Playwright screenshotter** capturing 1280×720 JPEG 80%
- **SQLite** database at `/home/ian/vibemill/data/vibemill.sqlite` as source of truth
- **Snapshot uploader** pushing state to Supabase project `vibemill-inventory`
- Logging via stdout + journalctl

## Do NOT build in v0

- The public-facing Next.js site at vibemill.dev
- Email subscriptions or the Resend integration
- Mode 2 user-submitted prompts
- Any archetype other than Tracker
- The cemetery page UI
- The rejection sidebar UI
- Rate limiting (no public surface yet)
- Authentication of any kind

If you find yourself wanting to build any of the above, **stop and ask the user.**

## Do NOT improve in any version

Read `ANTI_PATTERNS.md` for the full list. The headline rules:

- Do not switch to reasoning models for codegen — DeepSeek V3 chat is correct
- Do not improve the verification prompt — its shallowness is the satire
- Do not add hallucination suppression, fact-checking, or grounding
- Do not lower temperature on the generator below 0.7
- Do not filter visibly-broken outputs — they are the receipts
- Do not add post-deployment error monitoring on generated apps
- Do not "tighten" the readme persona — its tells are deliberate
- Do not advertise the satire in user-facing copy

## Document map

For implementation details, read these in order:

- **`THESIS.md`** — why this project exists at the intellectual level. Read first if you're trying to understand project intent; the operational docs explain the how, not the why.
- `ARCHITECTURE.md` — system topology, data flow, environments
- `STACK.md` — concrete library and version choices
- `migrations/supabase/001_init.sql` + `002_add_verifier_columns.sql` — canonical Postgres schema; SQLite mirrors at `migrations/sqlite/`
- `ARCHETYPES.md` — the 12 archetype specifications
- `MATCHER.md` — guard + judge prompts and logic
- `GENERATOR.md` — codegen + verification + retry policy
- **`ANTI_PATTERNS.md`** — what NOT to improve. Required reading.
- `VOICE.md` — brand voice for mill-authored copy
- `PERSONAS.md` — distinguishing mill voice from generated-readme voice
- `OPERATIONS.md` — rotation, rate limits, content policy, failure modes
- `SECURITY.md` — token handling, env vars, no-commit list
- `README.md` — dev setup and deploy steps
- `DIRECTORY.md` — repository structure

## Authorial voice for code comments and commit messages

- No em dashes
- No "genuinely" — use "truly" if needed, otherwise omit
- Peer register, not student register
- Direct, dry, slightly deadpan
- No marketing-speak ("seamlessly", "powerful", "revolutionary")
- No hyphens in informal contexts where they read AI-generated

This applies to commit messages, code comments, log strings, error messages, and any documentation produced by AI assistants on this project.

## Workflow rules

- Before any non-trivial code change, read the relevant document(s) above
- For decisions not covered in the documents, ask the user — do not improvise
- Prefer fewer abstractions to more; this is a small project
- No tests beyond a single end-to-end smoke test in v0
- All external API calls go through a single `clients/` module so they are swappable
- All prompts live in versioned files in `prompts/`, not inline in code
- When in doubt about whether to "improve" an LLM-output stage, default to *not* improving and surface the question

## The reference question

When uncertain whether a change is appropriate, ask:

> *Does the median vibecoder do this?*

If yes, Vibe Mill should do it.
If no, Vibe Mill should not.

Whether the change would make the artifacts cleaner, more correct, or more polished is irrelevant. Faithfulness to the genre is the operative constraint, not engineering quality.
