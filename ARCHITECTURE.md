# Architecture

Vibe Mill is composed of two systems that share state via Supabase. Each system has a different runtime and a different purpose.

## System A: Public site (vibemill.dev)

**Purpose:** display the feed, the cemetery, the rejection sidebar; accept Mode 2 prompt submissions; manage email subscriptions.

**Runtime:** Vercel free tier.

**Stack:** Next.js (defer specific version and patterns to Claude Code at implementation time). Reads from Supabase via the supabase-js client. Uses ISR with a 60-second revalidate window for the feed page.

**Not built in v0.** Specced here for completeness; deferred until orchestrator is stable.

## System B: Orchestrator (sunfamily)

**Purpose:** ingest news, score it, generate apps, deploy them, screenshot them, log everything to SQLite, push snapshots to Supabase.

**Runtime:** sunfamily.home.arpa, at `/home/ian/vibemill/`.

**Trigger:** systemd timer fires `vibemill.service` once per hour.

**Stack:** Python 3.12, no web framework. The orchestrator is a script, not a server. It runs to completion and exits.

**This is what V0 builds.**

## System C: Generated apps

**Purpose:** the artifacts the mill produces. Each is its own deployed Vercel project, with its own GitHub repo in the `vibemill-apps` org.

**Runtime:** Vercel free tier, capped at 100 concurrent live apps. Rotation policy described in `OPERATIONS.md`.

## Data flow per cron tick

```
                    ┌─────────────────────────────┐
                    │  systemd timer fires        │
                    │  vibemill.service           │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  ingest.py                  │
                    │  pull AP + BBC RSS          │
                    │  dedupe vs SQLite cache     │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  guard pass                 │  ← haiku via OpenRouter
                    │  reject sensitive content   │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │  matcher                    │  ← haiku via OpenRouter
                    │  score vs 12 archetypes     │
                    │  threshold 7                │
                    └─────────────┬───────────────┘
                                  │
            ┌─────────────────────┴─────────────────────┐
            │                                           │
       Rejected                                       Passed
            │                                           │
   ┌────────▼────────┐                       ┌──────────▼──────────┐
   │ log to SQLite   │                       │  generator.py       │  ← deepseek-v3
   │ rejections      │                       │  fill archetype     │     via OpenRouter
   │ + reason        │                       │  template slots     │
   └─────────────────┘                       └──────────┬──────────┘
                                                        │
                                              ┌─────────▼─────────┐
                                              │  github_publish   │
                                              │  create repo      │
                                              │  push code        │
                                              └─────────┬─────────┘
                                                        │
                                              ┌─────────▼─────────┐
                                              │  vercel_deploy    │
                                              │  create project   │
                                              │  poll until READY │
                                              └─────────┬─────────┘
                                                        │
                                              ┌─────────▼─────────┐
                                              │  screenshot.py    │
                                              │  playwright       │
                                              │  1280×720 JPEG    │
                                              └─────────┬─────────┘
                                                        │
                                              ┌─────────▼─────────┐
                                              │  log to SQLite    │
                                              │  apps table       │
                                              └─────────┬─────────┘
                                                        │
                                              ┌─────────▼─────────┐
                                              │  snapshot.py      │
                                              │  push to Supabase │
                                              └───────────────────┘
```

## Daily rotation tick

A separate systemd timer fires `vibemill-rotate.service` once per day at midnight local time. It:

1. Counts live apps in SQLite
2. If count > 100, retires the oldest non-viral apps until count == 100
3. Viral apps (10k views in a day OR 2k concurrent users at any point) are exempt from retirement; they receive a 30-day extension and are re-evaluated after
4. Retirement = archive GitHub repo + delete Vercel project + mark `status='archived'` in SQLite + push snapshot

## State management

**Source of truth:** SQLite at `/home/ian/vibemill/data/vibemill.sqlite`.

**Public mirror:** Supabase project `vibemill-inventory`. The orchestrator pushes snapshots after each cron tick. Eventual consistency is acceptable; the public site shows the last successful snapshot.

**Why split:** the orchestrator runs offline workloads with persistent local state; SQLite is the right tool. The public site needs a managed, internet-reachable database; Supabase is the right tool. We do not want the public site coupled to sunfamily's home internet uptime.

## Environments

**Development:** Ian's laptop. Claude Code runs here. Code is written here. A subset of the orchestrator can be run locally for testing (with a separate `.env.dev` pointing at a dev Supabase project or just SQLite).

**Production:** sunfamily.home.arpa. Code is deployed by `git pull && systemctl restart vibemill.timer`. Logs available via `journalctl -u vibemill.service`.

**No staging.** This is a small enough project that staging is overhead. If a deploy breaks production, fix forward.

## External services and their roles

| Service       | Role                                              | Tier        |
|---------------|---------------------------------------------------|-------------|
| OpenRouter    | LLM provider abstraction (haiku + DeepSeek V3)    | Pay-as-you-go |
| GitHub        | Repo hosting for `vibemill-apps`                  | Free        |
| Vercel        | Hosting for generated apps + (later) public site  | Free        |
| Supabase      | Public-facing state mirror                        | Free        |
| Resend        | Transactional email (deferred to v1)              | Free        |
| Porkbun       | Domain registrar (vibemill.dev)                   | $13/year    |
| Playwright    | Screenshot capture (local, on sunfamily)          | OSS         |

## Failure isolation

The orchestrator's stages are independent. If one fails, the others should not cascade. Specifically:

- Failure in the matcher pass should log and continue to the next news item
- Failure in the generator should mark the app as stillborn and continue
- Failure in GitHub publish should retry; on persistent failure, mark stillborn
- Failure in Vercel deploy should retry; on persistent failure, mark stillborn but keep the GitHub repo
- Failure in screenshot should ship the app without a screenshot, marked `screenshot_status='missing'`
- Failure in Supabase snapshot should retry on next tick; the local SQLite is the source of truth and is unaffected

Detailed retry policies live in `OPERATIONS.md`.
