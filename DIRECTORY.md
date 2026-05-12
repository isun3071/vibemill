# Directory

The expected layout of the `vibemill` repository. Claude Code creates this scaffold on first run; this document is the source of truth for what should exist.

## Top-level

```
vibemill/
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock                       # or poetry.lock
├── README.md
├── CLAUDE.md
├── ARCHITECTURE.md
├── STACK.md
├── ARCHETYPES.md
├── MATCHER.md
├── GENERATOR.md
├── VOICE.md
├── PERSONAS.md
├── OPERATIONS.md
├── SECURITY.md
├── DIRECTORY.md                  # this file
│
├── vibemill/                     # the python package
├── archetypes/                   # chassis + templates per archetype
├── prompts/                      # LLM prompt files
├── migrations/                   # SQL migrations
├── deploy/                       # systemd units, deploy scripts
├── public-site/                  # next.js site (V1+)
├── tests/                        # smoke test
├── scripts/                      # one-off operator scripts
└── data/                         # SQLite db lives here (gitignored)
```

## `vibemill/`

The Python package implementing the cron job. The entry point is `__main__.py`.

```
vibemill/
├── __init__.py
├── __main__.py                   # entry point: runs one cron tick
├── config.py                     # loads .env, exposes typed config
├── models.py                     # pydantic models for inter-module data
│
├── ingest.py                     # AP/BBC/Reuters/Al Jazeera/Wired RSS pull (40% pipeline)
├── synthetic_prompt.py           # Bundle G: synthetic hackathon-idea LLM (60% pipeline, Haiku)
├── tracks.py                     # Bundle G: hackathon-track taxonomy + sampler
├── tiers.py                      # three-tier output calibration (slop/mean_good/banger)
├── layouts.py                    # Bundle C: Tracker layout-archetype rotation
├── guard.py                      # guard model wrapper (claude haiku)
├── matcher.py                    # archetype matcher + blend logic (claude haiku)
├── generator.py                  # codegen (deepseek-v4-flash), substrate-aware (JS + Python)
├── readme_writer.py              # vibecoder-persona README generator
├── github_publish.py             # github org repo create + push
├── deploy.py                     # Bundle H: per-archetype deploy router (Vercel | HF Spaces)
├── vercel_deploy.py              # vercel project create + deploy
├── hf_spaces_deploy.py           # Bundle H: HF Space create + force-push for Python rail
├── screenshot.py                 # playwright screenshot
├── snapshot.py                   # push state to supabase
├── retire.py                     # rotation logic (called by separate cron)
│
├── db.py                         # sqlite + sqlmodel setup
├── audit.py                      # audit log helper
│
├── clients/                      # external service clients (swappable)
│   ├── __init__.py
│   ├── openrouter.py
│   ├── github.py
│   ├── vercel.py
│   ├── hf_spaces.py              # Bundle H: HF Spaces REST client (create/poll/delete)
│   ├── supabase.py
│   └── resend.py                 # V1+
│
├── cli.py                        # `python -m vibemill <command>` ops
├── smoke_test.py                 # end-to-end pipeline smoke test
└── name_generator.py             # adjective-noun-number subdomain names
```

## `archetypes/`

Chassis and example data per archetype. Bundle F: the buildable set is
`tracker`, `chatbot`, `utility_tool`, `search_directory`. Other archetypes
in the 13-archetype taxonomy exist as stubs and become buildable when
their chassis + prompt template land in a future bundle.

```
archetypes/
├── tracker/                      # buildable
│   ├── chassis/                  # thin scaffolding copied into every Tracker app
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── tailwind.config.ts
│   │   ├── postcss.config.js
│   │   ├── next.config.js
│   │   ├── .gitignore
│   │   ├── public/
│   │   │   └── favicon.ico       # vibemill mark (when present)
│   │   └── app/
│   │       ├── layout.tsx        # bare <main> + the mill footer disclaimer
│   │       └── globals.css       # just the @tailwind directives
│   │   # Note: NO lib/components — the LLM designs the page from inline JSX.
│   ├── slots.json                # describes which files the LLM produces
│   └── example/                  # one possible Tracker (also a build fixture)
│       ├── app/page.tsx
│       ├── lib/data.ts
│       └── README.md
│
├── chatbot/                      # buildable (Bundle F); chassis copy of tracker
├── utility_tool/                 # buildable (Bundle F)
├── search_directory/             # buildable (Bundle F)
│
├── parody_ui/                    # stub (in 13, not yet lit up)
├── glorified_todo/               # stub
├── glorified_social/             # stub
└── recommendation_engine/        # stub
# Not yet directory-stubbed (also in 13): ai_agent, ai_generator, game,
# marketplace, map_visualizer
```

## `prompts/`

Versioned prompt files. Each is plain text with `{{variable}}` placeholders.

```
prompts/
├── guard.txt                     # safety check prompt (haiku)
├── matcher.txt                   # 13-archetype scoring prompt (haiku, Bundle F)
├── synthetic_prompt.txt          # Bundle G: hackathon-idea generation (haiku, conditioned on track)
├── readme/                       # 12 README personas (Bundle E: +5 from 7)
│   ├── enthusiastic.txt
│   ├── minimalist.txt
│   ├── mlh_template.txt          # Devpost submission template filled in literally
│   ├── founder_hustle.txt        # building-in-public voice
│   ├── technical_maximalist.txt
│   ├── corporate.txt
│   ├── vibes.txt
│   ├── humble.txt
│   ├── chatgpt_loud.txt
│   ├── academic.txt              # research-paper register
│   ├── shitpost.txt              # ironic / self-aware
│   └── grindset.txt              # 48hr no-sleep energy
└── generator/
    ├── tracker/                  # Bundle C: layout-archetype rotation (8 layouts)
    │   ├── dashboard.txt         # ~30%
    │   ├── long_form.txt         # ~15%
    │   ├── map_dominant.txt      # ~15%
    │   ├── chart_dominant.txt    # ~10%
    │   ├── editorial.txt         # ~10%
    │   ├── card_feed.txt         # ~10%
    │   ├── list_dominant.txt     # ~5%
    │   └── split_view.txt        # ~5%
    ├── chatbot.txt               # Bundle F: conversational UI + Puter.js/LLM7 AI
    ├── utility_tool.txt          # Bundle F: single-purpose tool
    ├── search_directory.txt      # Bundle F: search + browse + detail view
    # Not yet lit up (matcher will route to "archetype not yet implemented"):
    # ai_agent, ai_generator, game, glorified_todo, glorified_social,
    # recommendation_engine, marketplace, map_visualizer, parody_ui
```

## `migrations/`

SQL migrations for both SQLite (local source of truth) and Supabase (public mirror). Both are kept in sync; SQLite migrations are derived from the Supabase ones with minor syntax differences.

```
migrations/
├── supabase/
│   └── 001_init.sql              # canonical Postgres schema
└── sqlite/
    └── 001_init.sql              # SQLite-compatible translation
```

## `deploy/`

Deployment artifacts.

```
deploy/
├── systemd/
│   ├── vibemill.service          # runs `python -m vibemill` once
│   ├── vibemill.timer            # fires hourly
│   ├── vibemill-rotate.service   # runs `python -m vibemill rotate`
│   └── vibemill-rotate.timer     # fires daily at midnight
└── install-hooks.sh              # installs git pre-commit hook
```

## `public-site/`

Next.js site for vibemill.dev. **Not implemented in V0.** Empty directory or absent at V0.

```
public-site/                      # V1+
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── next.config.js
├── app/
│   ├── layout.tsx
│   ├── page.tsx                  # the live feed
│   ├── cemetery/
│   │   └── page.tsx
│   ├── rejected/
│   │   └── page.tsx
│   ├── about/
│   │   └── page.tsx
│   ├── submit/
│   │   └── page.tsx
│   └── api/
│       ├── subscribe/route.ts
│       ├── unsubscribe/route.ts
│       └── submit/route.ts
└── lib/
    └── supabase.ts
```

## `tests/`

```
tests/
├── __init__.py
├── test_smoke.py                 # the end-to-end pipeline test
└── fixtures/
    ├── test_news.json            # canned news input for smoke test
    └── test_prompt.txt           # canned user prompt
```

## `scripts/`

One-off operator helpers. Not part of the normal cron flow.

```
scripts/
├── calibrate_matcher.py          # runs matcher on test inputs, prints scores
├── reset_dev_db.sh               # nukes local SQLite for fresh start
├── inspect_app.py                # prints all data for a given app_id
└── install-hooks.sh              # symlinked from deploy/
```

## `data/` (gitignored)

Created on first run by the orchestrator. Contains:

```
data/
├── vibemill.sqlite               # source of truth
├── vibemill.sqlite-journal       # SQLite WAL artifacts
├── screenshots/                  # local screenshot cache before upload
│   └── <app_id>.jpg
└── builds/                       # tempdir for `next build` runs (cleaned after)
```

## What lives where: a quick reference

| Question                          | Answer                                  |
|-----------------------------------|-----------------------------------------|
| Where is the cron entry point?    | `vibemill/__main__.py`              |
| Where do I edit the matcher prompt? | `prompts/matcher.txt`                 |
| Where is the Tracker chassis?     | `archetypes/tracker/chassis/`           |
| Where is the SQLite schema?       | `migrations/sqlite/001_init.sql`        |
| Where is the systemd timer?       | `deploy/systemd/vibemill.timer`         |
| Where do tokens go?               | `.env` (NOT committed)                  |
| Where does the smoke test live?   | `tests/test_smoke.py`                   |
| Where is the operator CLI?        | `vibemill/cli.py`                   |
