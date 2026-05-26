# Vibe Mill

Vibe Mill is an app machine. It grinds vibes into apps.

The mill produces vibecoded web applications from news headlines and synthetic hackathon prompts on a slow cadence, in bursts every four hours. The mill does not promise quality, does not promise relevance, and ships anyway. Output lives for twenty one days, then retires to a public cemetery with cause of death and total cost recorded.

This repository contains the orchestrator, the archetype templates, the prompts, and the Next.js public site that runs at [vibemill.dev](https://vibemill.dev).

- For the **backstory and intellectual frame**, why this project exists, the four pillars, the satirical method, and the precedents it sets, read [`THESIS.md`](./THESIS.md).
- For the **operational rules of what NOT to improve**, design choices that look like bugs but are load bearing for the satire, read [`ANTI_PATTERNS.md`](./ANTI_PATTERNS.md).
- For a **guided tour of the project's design**, the architecture, the archetypes, the voice separation, and the workflow rules, start with [`CLAUDE.md`](./CLAUDE.md).
- For the **release history**, including the bundle by bundle log of what changed and why, see [`CHANGELOG.md`](./CHANGELOG.md).

## Current state

The mill ships across three deploy rails, all thirteen archetypes buildable:

- **Next.js on Vercel**: tracker, chatbot, utility_tool, search_directory
- **Gradio on Hugging Face Spaces**: ai_generator, ai_agent (bring your own key, the demo is broken until the reader supplies an OpenAI key in the Space's secrets)
- **Flask on GitHub only**: glorified_todo, parody_ui, marketplace, map_visualizer, recommendation_engine, game, glorified_social

Every app is published as a GitHub repo and, where applicable, a live deployment. Every app's README opens with a short disclaimer noting that the artifact was produced by an automated pipeline with no human contribution. Every app also ships an `mlh.md` sidecar, a Devpost format pitch that runs through a tier driven voice picker so banger output reads like a real prize winner while slop output reads like a cargo cult Devpost.

Apps cost between five and seventy cents to produce, depending on tier. The average is about thirty cents. The full economic comparison sits in `THESIS.md`.

## Repository layout

```
vibemill/
├── vibemill/             # python package: the orchestrator
│   ├── __main__.py       # cron tick entrypoint
│   ├── generator.py      # LLM driven app generation
│   ├── matcher.py        # archetype + score routing
│   ├── readme_writer.py  # README persona + mlh sidecar voice palette
│   ├── github_publish.py # tier driven commit history + push
│   ├── vercel_deploy.py  # Next.js rail
│   ├── hf_spaces_deploy.py # Gradio rail
│   └── clients/          # OpenRouter, Tavily, Vercel, Supabase wrappers
├── archetypes/           # chassis files per substrate
├── prompts/              # versioned LLM prompts (generator, matcher, guard, readme, mlh)
├── migrations/           # SQLite + Supabase schema
├── deploy/systemd/       # systemd unit files for the cron host
├── public-site/          # Next.js site at vibemill.dev
└── tests/                # smoke test
```

## Prerequisites

You need accounts on the following services, set up roughly in this order:

1. **GitHub organization** for the generated apps (the project default is `vibemill-apps`). Create a fine grained personal access token scoped to that org.
2. **Vercel account**, with the Vercel GitHub app installed on the apps org. Generate an API token.
3. **OpenRouter account**, with a payment method and a daily spending cap. Generate an API key. The mill uses DeepSeek V4 Flash for generation and Claude Haiku for guard, matcher, and readme tasks.
4. **Tavily account** for web search grounding on the mean_good and banger tiers. Generate an API key.
5. **Hugging Face account** with write access. Generate an access token. This rail hosts the Gradio (Python AI) apps.
6. **Supabase project** for the public mirror that backs vibemill.dev. Apply the migrations in `migrations/supabase/`, then collect the project URL and the service role key.
7. **A domain**, if you want the public site to have one. The mill itself works fine without a domain.

## Local development setup

On your laptop:

```bash
git clone https://github.com/<your-user>/vibemill
cd vibemill

uv sync                                  # install python deps
uv run playwright install chromium       # for the screenshot step
sudo uv run playwright install-deps chromium  # system libs

cp .env.example .env                     # populate with your tokens
chmod 600 .env

mkdir -p data
sqlite3 data/vibemill.sqlite < migrations/sqlite/001_init.sql
# Then apply migrations 002 through the latest in numeric order.

uv run python -m vibemill                # run one cron tick
```

The orchestrator is safe to run on a laptop. It will publish to your GitHub org and deploy to your Vercel team. Costs per tick are bounded by the daily cap configured in `.env`.

## Production deployment

The mill is designed to run as two systemd timers on a small Ubuntu box: the main timer fires every four hours, and a rotation timer fires daily to retire apps past their twenty one day window.

On the server:

```bash
# Clone, install deps, scp your .env and data/ directory from your laptop,
# then fix any hardcoded /home/<your-user>/ paths inside .env.

cd ~/vibemill
uv sync
uv run playwright install chromium
sudo uv run playwright install-deps chromium

# Make sure the writable cache dirs exist before the sandboxed service tries
# to bind mount them.
mkdir -p ~/.cache/uv ~/.npm

# Install the units
sudo cp deploy/systemd/vibemill.service        /etc/systemd/system/
sudo cp deploy/systemd/vibemill.timer          /etc/systemd/system/
sudo cp deploy/systemd/vibemill-rotate.service /etc/systemd/system/
sudo cp deploy/systemd/vibemill-rotate.timer   /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now vibemill.timer vibemill-rotate.timer

# Verify
systemctl list-timers vibemill\*
journalctl -u vibemill.service -f
```

The unit files default to user `ian` and path `/home/ian/vibemill`. If your server uses different values, edit `deploy/systemd/*.service` accordingly before copying.

## Updating production

```bash
ssh <user>@<server>
cd ~/vibemill
git pull
uv sync                                  # only if dependencies changed
# Code and prompt changes load on the next tick. No service restart needed
# unless a unit file changed.
# To fire a tick immediately rather than wait for the timer:
sudo systemctl start vibemill.service
journalctl -u vibemill.service -f
```

## Manual operations

```bash
# Run one full tick (same as what the timer fires)
uv run python -m vibemill

# Run one app end to end with a chosen archetype, for development
uv run python -m vibemill.cli ship-one --archetype tracker

# Retire one specific app early
uv run python -m vibemill retire <app-id>

# Daily rotation, normally fired by the rotation timer
uv run python -m vibemill rotate
```

## Costs

Approximate operating cost at the current cadence of roughly six ticks a day, with one or two apps shipping per tick:

| Service          | Cost                                |
|------------------|-------------------------------------|
| OpenRouter       | $5 to $15 / month                   |
| Tavily           | $0 to $5 / month (free tier first)  |
| GitHub           | $0 (free org)                       |
| Vercel           | $0 (free team tier)                 |
| Hugging Face     | $0 (free Spaces)                    |
| Supabase         | $0 (free tier)                      |
| Domain           | ~$1 / month amortized               |
| Server           | $0 marginal if you already run one  |

**Total: $5 to $25 / month.**

The cost ledger inside the orchestrator tracks every LLM call so the daily cap can be enforced before a runaway tick burns the budget.

## License

The orchestrator code is MIT licensed.

Generated apps in the apps org are not licensed for reuse. They are satirical artifacts. The code is mostly broken, the README files lie, and the data is hardcoded. Reuse should be considered carefully.

## Authorship and credits

Concept and direction: Ian Sun.

Built with Claude Code. The orchestrator, the thesis, the anti pattern rules, and the other markdown documents in this repository were written in conversation with Claude over a series of pair programming sessions. The artifacts the orchestrator itself produces, in contrast, involve no human at all. That distinction is the load bearing point of the project, and is unpacked in `THESIS.md`.

The premise inherits from Andrej Karpathy's [February 2025 description of vibe coding](https://x.com/karpathy/status/1886192184808149383), Riley Walz and Luke Igel's Jmail as the friction inversion satirical archetype, and the broader cultural moment in which "shipped a thing using AI" became a credentialing claim that no longer differentiates anyone.
