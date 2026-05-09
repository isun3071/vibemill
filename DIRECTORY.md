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
├── ingest.py                     # AP + BBC RSS pull
├── guard.py                      # guard model wrapper (claude haiku)
├── matcher.py                    # archetype matcher (claude haiku)
├── generator.py                  # codegen (deepseek-v3)
├── readme_writer.py              # vibecoder-persona README generator
├── github_publish.py             # github org repo create + push
├── vercel_deploy.py              # vercel project create + deploy
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
│   ├── supabase.py
│   └── resend.py                 # V1+
│
├── cli.py                        # `python -m vibemill <command>` ops
├── smoke_test.py                 # end-to-end pipeline smoke test
└── name_generator.py             # adjective-noun-number subdomain names
```

## `archetypes/`

Chassis and example data per archetype. V0 only fills `tracker/`.

```
archetypes/
├── tracker/
│   ├── chassis/                  # files copied verbatim into every Tracker app
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── tailwind.config.ts
│   │   ├── postcss.config.js
│   │   ├── next.config.js
│   │   ├── .gitignore
│   │   ├── public/
│   │   │   └── favicon.ico       # vibemill mark
│   │   ├── app/
│   │   │   └── layout.tsx        # includes the mill footer disclaimer
│   │   └── lib/
│   │       └── components/
│   │           ├── Counter.tsx
│   │           ├── MapPanel.tsx
│   │           ├── Timeline.tsx
│   │           └── NewsList.tsx
│   ├── slots.json                # describes which files the LLM produces
│   └── example/                  # one fully-working example for reference
│       ├── app/page.tsx
│       ├── lib/data.ts
│       └── README.md
│
├── parody-ui/                    # stub in V0 (only directory exists)
├── case-file-browser/            # stub
├── counter-game/                 # stub
├── disruption-visualizer/        # stub
├── diaspora-map/                 # stub
├── legal-action-tracker/         # stub
├── mutual-aid-coordinator/       # stub
├── wordle-redux/                 # stub
├── glorified-todo/               # stub
├── glorified-social/             # stub
└── recommendation-engine/        # stub
```

## `prompts/`

Versioned prompt files. Each is plain text with `{{variable}}` placeholders.

```
prompts/
├── guard.txt                     # safety check prompt (haiku)
├── matcher.txt                   # 12-archetype scoring prompt (haiku)
├── readme.txt                    # vibecoder-persona README prompt (cheap model)
└── generator/
    ├── tracker.txt               # codegen prompt for Tracker (deepseek-v3)
    ├── parody-ui.txt             # V1+
    ├── case-file-browser.txt     # V1+
    ├── counter-game.txt          # V1+
    ├── disruption-visualizer.txt # V1+
    ├── diaspora-map.txt          # V1+
    ├── legal-action-tracker.txt  # V1+
    ├── mutual-aid-coordinator.txt # V1+
    ├── wordle-redux.txt          # V1+
    ├── glorified-todo.txt        # V1+
    ├── glorified-social.txt      # V1+
    └── recommendation-engine.txt # V1+
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
