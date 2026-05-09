# Generator

The generator takes a prompt + a selected archetype and produces a deployable Next.js app. It uses DeepSeek V3 via OpenRouter.

## The chassis-and-slots model

Every archetype has a **chassis** (fixed scaffolding written by us, copied verbatim into every generated app of that archetype) and **slots** (files the LLM produces from a templated prompt).

The chassis includes:
- `package.json` with pinned dependencies
- `tailwind.config.ts`
- `tsconfig.json`
- `.gitignore`
- `app/layout.tsx` (with the Vibe Mill footer disclaimer baked in)
- `lib/components/` (archetype-specific UI primitives)
- `public/favicon.ico` (the Vibe Mill mark)

The slots are produced by the LLM:
- `app/page.tsx` (the main page content)
- `lib/data.ts` (the data definitions for this specific app)
- `app/api/` routes if the archetype needs them (Tracker does not in V0)
- `README.md` (machine-authored, see PERSONAS.md)

Slot files are written to disk after the LLM produces them. Then chassis + slots are committed together as a single git repo and pushed.

## Why this architecture

**Output token economy.** A full Next.js app is 50k+ tokens to generate. Letting the LLM write only the slots (typically 5-15k tokens) cuts cost and latency significantly.

**Failure mode reduction.** The chassis files are pre-tested. If the LLM produces broken slot code, the build still has known-good infrastructure around it; the failure surface is smaller.

**Brand consistency.** The footer disclaimer, favicon, meta tags, and consistent Tailwind config come from the chassis. The LLM cannot accidentally remove the disclaimer.

**Faster iteration.** When we improve the chassis, all *future* apps benefit; existing archived apps stay frozen as artifacts.

## Generator prompt template

The generator prompt is a Jinja-style template at `prompts/generator/{archetype}.txt`. For V0 the only one needed is `prompts/generator/tracker.txt`.

### `prompts/generator/tracker.txt`

```
You are generating a Next.js 14 (App Router) page for a satirical
news-tracker app called Vibe Mill. The app is a Tracker archetype:
a small dashboard showing quantitative state of an ongoing event.

Context:
- Prompt: {{prompt}}
- News source: {{source_url}}
- News headline: {{source_headline}}
- News summary: {{source_summary}}

Your output produces three files. The chassis (layout, components,
config) already exists; do not produce those.

Produce in JSON only, with three keys:

{
  "page_tsx": "the full content of app/page.tsx",
  "data_ts": "the full content of lib/data.ts",
  "readme_md": "the full content of README.md"
}

Constraints for app/page.tsx:
- Use the App Router (this is a Server Component by default, no "use client" unless needed for charts)
- Import primitives from @/lib/components: Counter, MapPanel, Timeline, NewsList
- Import data from @/lib/data
- Render: header with title and tagline, main grid with Counter cards, MapPanel, Timeline, NewsList
- Tailwind utility classes only; no custom CSS
- The footer disclaimer is rendered by the chassis layout; do not include one in page.tsx

Constraints for lib/data.ts:
- Export typed data: title, tagline, counters[], regions[], timelineEvents[], newsItems[]
- Use TypeScript inferred types where reasonable; explicit types for the exported objects
- Data must be structurally complete: every Counter has label and value, every region has name and status, every timeline event has date and description
- Hardcode reasonable values based on the source; do not fetch external data
- The data is baked in at build time and represents the state when the app was milled

Constraints for README.md:
- Sound like a hackathon project README written by an enthusiastic solo developer
- Include emoji headers (🚀 Overview, 📦 Installation, 🛠️ Tech Stack, 📊 Future Work)
- Include cliché phrases like "passion project" or "built in a weekend"
- The last paragraph should subtly tip its hand: machine-authored language seeping through
- Do NOT mention Vibe Mill by name; the readme persona believes a human wrote it

Style for page.tsx:
- Visually polished surface (good spacing, hierarchy, color contrast)
- Functional logic: dashboards display the data; clicking elements should not break anything but does not need to do interesting things
- The app must build cleanly with `next build` against the chassis

Output the JSON object only. No prose before or after.
```

### Variable substitution

The orchestrator substitutes `{{prompt}}`, `{{source_url}}`, `{{source_headline}}`, `{{source_summary}}` before sending to the LLM.

## Retry policy

The generator is allowed **one retry** on failure. The retry strategies are:

### Failure mode 1: malformed JSON output

The orchestrator parses the LLM response against a pydantic model. If parsing fails:
- Retry once with the malformed output appended to the prompt and an instruction: "your previous output was not valid JSON. Fix it and respond again with valid JSON only."
- If retry fails, ship as stillborn with `death_cause='never_built'`.

### Failure mode 2: build failure

After writing slot files alongside the chassis, the orchestrator runs `next build` locally on sunfamily to verify the app compiles. If the build fails:
- Retry once with the build error appended to the prompt and an instruction: "your previous output produced a build error. Here is the error: ... Fix the issue and produce the same JSON structure again."
- If retry fails, ship as stillborn with `death_cause='never_built'`.

### Failure mode 3: build succeeds but app crashes at runtime

For V0, we do not test runtime behavior. If the app crashes when visited, that is on-brand and acceptable. Mark `screenshot_status='captured'` if a screenshot was obtained even if it shows an error page; mark `screenshot_status='missing'` if Playwright failed.

## Cost expectations

DeepSeek V3 via OpenRouter is approximately $0.27 per million output tokens. A typical Tracker generation:

- Input: ~3k tokens (prompt template + context)
- Output: ~6-12k tokens (three files)
- Cost per generation: $0.002 to $0.004
- With one retry on average for 30% of generations: $0.003 to $0.006 effective cost

Per-app total LLM cost (guard + matcher + generator + readme): under $0.05.

## Smoke test

The orchestrator must include a single end-to-end smoke test that exercises the full pipeline against a hardcoded "test news event" without touching production GitHub or Vercel. The test:

1. Loads a fixed test prompt
2. Runs guard (must pass)
3. Runs matcher (must select Tracker)
4. Runs generator
5. Verifies the output is valid JSON
6. Writes files alongside the chassis
7. Runs `next build` in a temp directory
8. Asserts build succeeds

The test does NOT push to GitHub, deploy to Vercel, or take a screenshot. It exercises the LLM pipeline only.

Run via: `python -m vibemill.smoke_test`.
