# Stack

Concrete tooling choices for Vibe Mill. Each choice is justified by what the workload needs, not by what is hip.

## Orchestrator (System B, V0)

### Language
**Python 3.12.** Modern enough for `match` statements, type unions with `|`, and current asyncio idioms. Available on most Linux distros without pyenv.

### Package management
**uv** (preferred) or **poetry**. Both work. Lock dependencies in `pyproject.toml` + lockfile. No raw `pip install`.

### HTTP
**httpx** (async). Used for all external API calls: OpenRouter, GitHub, Vercel, Supabase. Sync httpx is acceptable for the ingestion stage if simpler.

### LLM provider
**OpenRouter.** Single API endpoint, swappable models. Two distinct calls used:
- Guard + matcher: `anthropic/claude-haiku-4.5` (cheap, strong refusal posture)
- Generator: `deepseek/deepseek-chat-v3` (cheap, decent code output)

Both routed through `clients/openrouter.py` so swapping models is one config change.

### Validation and models
**pydantic v2.** All LLM outputs are parsed against pydantic models. All inter-module data transfer uses pydantic models, not raw dicts.

### Database
**SQLite** via the standard library `sqlite3` module, accessed through **sqlmodel** for typed queries. Database file at `/home/ian/vibemill/data/vibemill.sqlite`.

Migrations: handwritten SQL in `migrations/` directory, applied in order on orchestrator startup.

### Git operations
**GitPython** (`gitpython` package) for local git operations (init, commit, push). GitHub API calls use httpx directly against the REST API.

### Browser automation
**playwright** for Python. Headless Chromium. Browser binary installed via `playwright install chromium`.

### Logging
**Standard library `logging`.** stdout-only. Captured by systemd journal via journalctl. No structured logging in v0; revisit if needed.

### Configuration
**python-dotenv** for `.env` file loading. All secrets and environment-specific config via env vars, never hardcoded.

### Scheduling
**systemd timer** on sunfamily. Two units:
- `vibemill.timer` + `vibemill.service`: hourly
- `vibemill-rotate.timer` + `vibemill-rotate.service`: daily at midnight

Service files live in `/etc/systemd/system/` on sunfamily. Source of truth in `deploy/systemd/` in the repo.

## Public site (System A, deferred to V1)

Defer specific stack choices to Claude Code at implementation time. Constraints to honor:

- Must deploy to Vercel
- Must read from Supabase via supabase-js
- Must use ISR or equivalent (revalidate ~60s) for the feed
- Must support a one-page form for Mode 2 submissions
- Must handle subscribe/unsubscribe via API routes, not separate backend

Reasonable default: **Next.js 14+ with App Router, Tailwind CSS, shadcn/ui components, supabase-js for data.** Claude Code may diverge if it has reason to.

## Generated apps (System C)

Each generated app is a **Next.js 14+ App Router project**. The generator produces:
- `package.json` with pinned dependencies
- `app/` directory with `layout.tsx`, `page.tsx`, and any archetype-specific routes
- `tailwind.config.ts`
- `tsconfig.json`
- `README.md` (machine-authored, persona per `PERSONAS.md`)
- `.gitignore`

**Why Next.js for generated apps:** Vercel's first-class support means deploys "just work" with zero config. The orchestrator does not configure builds; it pushes a Next.js project and Vercel handles the rest.

**Why Tailwind:** generated code with utility classes is more constrainable than freeform CSS. Reduces failure modes.

**Why pinned dependencies:** apps live for ~11 days then archive. We do not want a dep update breaking an archived app retroactively.

## External account setup (one-time, manual)

These accounts must exist before V0 runs. Setup is manual; not automated.

| Account                          | Purpose                                  |
|----------------------------------|------------------------------------------|
| GitHub org `vibemill-apps`       | Holds generated app repos                |
| GitHub repo `vibemill`           | Holds the orchestrator + docs codebase   |
| Vercel account, GitHub-linked    | Deploys generated apps                   |
| Vercel app installed on org      | Vercel can see `vibemill-apps` repos     |
| OpenRouter account               | LLM API access                           |
| Supabase project `vibemill-inventory` | Public-facing state mirror          |
| Porkbun domain `vibemill.dev`    | Public site (V1)                         |

Tokens for each are stored in `.env` (see `SECURITY.md`).

## What we are NOT using and why

| Thing                          | Why not                                                  |
|--------------------------------|----------------------------------------------------------|
| Django                         | Overkill; we are not building a CRUD app with users      |
| Flask                          | FastAPI superseded it for new projects; we use neither   |
| MongoDB                        | Our data is relational; SQLite/Postgres fit better       |
| Celery / Redis                 | systemd timer is enough; no need for a queue             |
| Docker                         | One Python process on one machine; containers add nothing|
| Kubernetes                     | See above                                                |
| LangChain / LlamaIndex         | We make ~3 LLM calls per cron tick; abstraction wastes effort |
| CrewAI / AutoGen / agentic frameworks | Our pipeline is deterministic; no agent planning needed |
| AWS / GCP / Azure              | Sunfamily + free tiers cover everything                  |

## Version pinning policy

Orchestrator: pin all top-level dependencies in `pyproject.toml`. Lock transitive deps via `uv.lock` or `poetry.lock`. Bump deliberately, not opportunistically.

Generated apps: pin all dependencies in their `package.json`. Use exact versions, not `^` or `~`. Each app is an immutable artifact once shipped.
