# Vibe Mill

> *"The profession is being dramatically refactored as the bits contributed by the programmer are increasingly sparse and between."*
> — Andrej Karpathy, December 2025

Vibe Mill is a satirical app machine. It produces vibe-coded web applications from news headlines and synthetic hackathon prompts on a slow cadence (5–10 per day, in bursts every 4 hours). The mill does not promise quality. The mill does not promise relevance. The mill ships.

This document is the operating manual for any AI assistant working on this codebase.

## What this project is

Vibe Mill is the industrialization of vibe coding as critique. Every app it produces is a counter-example to the resume bullet "shipped MVP using AI tools." The artifacts make the argument; we do not write a manifesto.

For the deeper intellectual framing, read `THESIS.md`. For the operational rules of *what not to improve*, read `ANTI_PATTERNS.md`. The first explains why the project exists; the second explains why "improvements" that look obvious are usually wrong.

The mill operates honestly:
- Every generated app discloses, in its README and footer, that it was machine-produced
- The mill does not pretend its output is human craft
- The mill respects content safety (inherits guard-model refusals)

## What this project is NOT

Vibe Mill is **not** a productivity tool, an AI startup, an engineering exercise in agentic AI, a vibe-coding platform for users, a tracker aggregator, a news service, or a portfolio piece intended to look impressive.

If a design decision starts to push toward any of those, push back.

## Critical: read ANTI_PATTERNS.md before improving anything

This codebase contains design choices that *look* like bugs but are intentional. Hallucination, overconfidence, shallow self-verification, and deliberately mid-quality outputs are load-bearing for the satire.

**Before improving any LLM call, prompt, or output, read `ANTI_PATTERNS.md`.** Drift toward "make it better" is the most predictable failure mode for contributors to this project.

## Current state

Three deploy rails, all 13 archetypes buildable:

- **nextjs / Vercel:** tracker, chatbot, utility_tool, search_directory
- **gradio / HF Spaces:** ai_generator, ai_agent (BYOK)
- **flask / github_only:** glorified_todo, parody_ui, marketplace, map_visualizer, recommendation_engine, game, glorified_social

Per-archetype substrate routing via `models.SUBSTRATE_BY_ARCHETYPE`. Banger tier runs a polish pass after the build check (Bundle K Lever 3). Every repo ships with both a `README.md` (honest about the code) and an `mlh.md` (Devpost-format pitch, allowed to oversell freely). Operational disclosure is prepended to both. Public site at `public-site/` (Next.js, SSR, Supabase-backed grid + pagination + cemetery + rejection sidebar + mill-status indicator). Full bundle history in `CHANGELOG.md`.

## Document map

- **`THESIS.md`** — why this project exists. Read for intent.
- **`ANTI_PATTERNS.md`** — what NOT to improve. Required before any LLM-stage change.
- `ARCHITECTURE.md` — system topology, data flow
- `STACK.md` — library and version choices
- `ARCHETYPES.md` — archetype specifications
- `OPERATIONS.md` — rotation, rate limits, failure modes
- `SECURITY.md` — token handling, env vars
- `VOICE.md` + `PERSONAS.md` — voice separation (mill voice vs readme voice)
- `CHANGELOG.md` — bundle history

## Authorial voice (code comments, commit messages, log strings)

- No em dashes
- No "genuinely" — use "truly" if needed, otherwise omit
- Peer register, not student register
- Direct, dry, slightly deadpan
- No marketing-speak ("seamlessly", "powerful", "revolutionary")

The readme writer is a separate persona that does NOT follow these rules; it deliberately uses marketing-speak. See `PERSONAS.md`.

## Workflow rules

- For non-trivial changes, read the relevant doc first
- For decisions not covered in docs, ask the user; do not improvise
- Prefer fewer abstractions to more
- All external API calls go through `clients/`
- All prompts live in `prompts/`, not inline
- When in doubt about whether to "improve" an LLM stage, default to NOT improving

## The reference question

When uncertain whether a change is appropriate, ask:

> *Does the median vibecoder do this?*

If yes, Vibe Mill should. If no, it shouldn't. Engineering quality is irrelevant; faithfulness to the genre is the constraint.
