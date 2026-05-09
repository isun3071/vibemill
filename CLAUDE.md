# Vibe Mill

> "There's a new kind of coding I call 'vibe coding', where you fully give in to the vibes, embrace exponentials, and forget that the code even exists."
> — Andrej Karpathy, February 2, 2025

Vibe Mill is a satirical app machine. It produces vibe-coded web applications from news headlines and one-line user prompts on a slow cadence (5–10 per day). The mill does not promise quality. The mill does not promise relevance. The mill ships.

This document is the operating manual for any AI assistant (Claude Code, Cursor, etc.) working on this codebase.

## What this project is

Vibe Mill is the industrialization of vibe coding as critique. Every app it produces is a counter-example to the resume bullet "shipped MVP using AI tools." The artifacts make the argument; we do not write a manifesto.

The satire is bounded. The mill operates honestly:

- Every generated app discloses, in its footer, that it was machine-produced
- The mill does not pretend its output is human craft
- The mill respects content safety (inherits guard-model refusals)
- The mill does not spam (one email per ship, real unsubscribe)

## What this project is not

Vibe Mill is **not** a productivity tool, an AI startup, an engineering exercise in agentic AI, a vibe-coding platform for users, a tracker aggregator, a news service, or a portfolio piece intended to look impressive.

If a design decision starts to push toward any of those, push back.

## V0 scope (what to build first)

Implement only the following in v0:

- **Orchestrator** at `/home/ian/vibemill/` on sunfamily, run hourly via systemd timer
- **News ingestion** from AP and BBC RSS feeds
- **Guard model pass** (claude haiku via OpenRouter) for content safety; rejects inherit LLM refusal
- **Matcher** (claude haiku via OpenRouter) scoring against the **Tracker** archetype only; threshold 7
- **Code generator** (DeepSeek V3 via OpenRouter) producing Tracker apps
- **GitHub publisher** creating repos in the `vibemill-apps` org
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

## Document map

For implementation details, read these in order:

- `ARCHITECTURE.md` — system topology, data flow, environments
- `STACK.md` — concrete library and version choices
- `migrations/supabase/001_init.sql` — canonical Postgres schema; `migrations/sqlite/001_init.sql` is the SQLite translation
- `ARCHETYPES.md` — the 12 archetype specifications
- `MATCHER.md` — guard + judge prompts and logic
- `GENERATOR.md` — codegen prompt template and retry policy
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
