# Vibe Mill

Vibe Mill is an app machine. It grinds vibes into apps.

The mill produces vibe-coded web applications from news headlines and one-line user prompts on a slow cadence (5–10 per day). The mill does not promise quality. The mill does not promise relevance. The mill ships.

This repository contains the orchestrator, archetype templates, and the public site at [vibemill.dev](https://vibemill.dev).

- For the **backstory and intellectual frame** — why this project exists, the four pillars, the satirical method, the precedents it sets — read [`THESIS.md`](./THESIS.md).
- For the **operational rules of what NOT to improve** — load-bearing anti-patterns that look like bugs but are not — read [`ANTI_PATTERNS.md`](./ANTI_PATTERNS.md).
- For a **guided tour of the project's design** — architecture, archetypes, voice separation, workflow rules — start with [`CLAUDE.md`](./CLAUDE.md).

## V0 status

V0 implements the orchestrator only. The public site (vibemill.dev) is V1+.

V0 ships:

- News ingestion from AP and BBC RSS feeds
- A two-pass safety + scoring pipeline (guard + matcher)
- A code generator producing one archetype (Tracker)
- Auto-publish to GitHub org `vibemill-apps` and auto-deploy to Vercel
- Screenshots via Playwright
- SQLite + Supabase state management
- Hourly cron + daily rotation cron via systemd

V0 does NOT ship:

- The public-facing site
- Email subscriptions
- User-submitted prompts
- Archetypes other than Tracker

## Repository layout

See `DIRECTORY.md` for the full tree. High-level:

```
vibemill/
├── vibemill/           # the python package that runs hourly
├── archetypes/         # chassis + templates per archetype
├── prompts/            # versioned LLM prompt files
├── migrations/         # SQLite + Supabase migrations
├── deploy/systemd/     # systemd unit files for sunfamily
├── public-site/        # Next.js site for vibemill.dev (V1+)
└── tests/              # smoke test
```

## Prerequisites

You need the following accounts, set up in this order:

1. **GitHub org `vibemill-apps`** — create at github.com → "New organization" → free plan
2. **GitHub PAT** — fine-grained, scoped to `vibemill-apps`, with permissions per `SECURITY.md`
3. **Vercel account, GitHub-linked** — install the Vercel GitHub app on `vibemill-apps`
4. **Vercel API token** — generate at vercel.com → Settings → Tokens
5. **OpenRouter account** — sign up, add payment method, set spending cap
6. **OpenRouter API key** — generate from the dashboard
7. **Supabase project `vibemill-inventory`** — create at supabase.com → New project → free tier
8. **Run migrations** — execute `migrations/supabase/*.sql` against the Supabase project (SQL editor in Supabase dashboard)
9. **Get Supabase credentials** — Project URL and service role key from Settings → API

10. **Domain `vibemill.dev`** — registered at Porkbun for V1+; not needed for V0

## Local development setup

On your laptop:

```bash
# Clone the repo
git clone https://github.com/<ian>/vibemill
cd vibemill

# Install Python dependencies
uv sync   # or: poetry install

# Install Playwright browser
uv run playwright install chromium

# Copy the env template and populate
cp .env.example .env
# Edit .env with your tokens

# Apply local SQLite migrations
mkdir -p data
sqlite3 data/vibemill.sqlite < migrations/sqlite/001_init.sql

# Run the smoke test
uv run python -m vibemill.smoke_test

# Run a single cron tick locally
uv run python -m vibemill
```

The smoke test exercises the LLM pipeline end-to-end without touching production GitHub or Vercel. See `GENERATOR.md` for details.

## Sunfamily deployment

On sunfamily.home.arpa:

```bash
# First-time setup
sudo mkdir -p /home/ian/vibemill
sudo chown ian:ian /home/ian/vibemill
cd /home/ian
git clone https://github.com/<ian>/vibemill

# Install dependencies (assumes uv is installed; if not: pipx install uv)
cd vibemill
uv sync
uv run playwright install chromium

# Populate the production .env
cp .env.example .env
# Edit .env with production tokens

# Apply migrations
sqlite3 data/vibemill.sqlite < migrations/sqlite/001_init.sql

# Install systemd units
sudo cp deploy/systemd/vibemill.service /etc/systemd/system/
sudo cp deploy/systemd/vibemill.timer /etc/systemd/system/
sudo cp deploy/systemd/vibemill-rotate.service /etc/systemd/system/
sudo cp deploy/systemd/vibemill-rotate.timer /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now vibemill.timer
sudo systemctl enable --now vibemill-rotate.timer

# Verify
systemctl status vibemill.timer
systemctl status vibemill-rotate.timer
journalctl -u vibemill.service -f
```

## Updating production

```bash
ssh sunfamily
cd /home/ian/vibemill
git pull
uv sync   # if dependencies changed
# Apply any new migrations:
# sqlite3 data/vibemill.sqlite < migrations/sqlite/00X_xxx.sql
sudo systemctl restart vibemill.timer
journalctl -u vibemill.service -f   # watch the next tick
```

## Manual operations

```bash
# Print current status
uv run python -m vibemill status

# Manually retire an app
uv run python -m vibemill retire melancholy-ferret-2847

# Run smoke test
uv run python -m vibemill smoke-test
```

## Costs

Approximate monthly costs at the V0 cadence (1-5 apps shipped per day):

| Service       | Cost                          |
|---------------|-------------------------------|
| OpenRouter    | $5–15                          |
| GitHub        | $0 (free)                      |
| Vercel        | $0 (free tier, capped at 100 apps) |
| Supabase      | $0 (free tier)                 |
| Resend (V1+)  | $0 (free tier, 3k emails/mo)   |
| Domain        | ~$1/month amortized            |
| Sunfamily     | $0 marginal (already running)  |

**Total: $5–20/month.**

## License

The orchestrator code is MIT licensed.

Generated apps in `vibemill-apps/*` are not licensed; they are satirical artifacts and any reuse should be considered carefully (the code is mostly broken, the readmes lie, and the data is hardcoded).

## Credits

Concept: Ian Sun.

Built with Claude Code.

The premise inherits from Andrej Karpathy's February 2025 description of vibe coding, Riley Walz and Luke Igel's Jmail (the friction-inversion satirical archetype), and the broader cultural moment in which "shipped a thing using AI" became a credentialing claim that no longer differentiates anyone.

The mill ships.
