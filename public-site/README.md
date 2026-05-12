# vibemill.dev — public site

The public-facing site for Vibe Mill. Reads from the Supabase mirror; never writes.

## Stack

- Next.js 14.2 App Router, React 18 (matches the generated-app chassis)
- Tailwind 3.4
- Source Serif 4 (body) + JetBrains Mono (metadata) via `next/font/google`
- `@supabase/supabase-js` 2.x, anon key only

## Run locally

```bash
cd public-site
cp .env.example .env.local   # fill in Supabase URL + anon key
npm install
npm run dev
```

Then visit http://localhost:3000.

## Deploy

A separate Vercel project, root directory `public-site/`, pointed at `vibemill.dev`. The orchestrator is unaffected.

## Pages

- `/` — hero + today's grid + about teaser
- `/about` — full thesis (stub)
- `/cemetery` — retired apps
- `/rejected` — guard / matcher rejections
- `/apps/[id]` — per-app detail (screenshot, links, operating data)

## Content guarantee

This site reads `apps`, `rejections`, `news_cache` via the Supabase anon key. RLS in `migrations/supabase/001_init.sql` constrains it to SELECT on those three tables.
