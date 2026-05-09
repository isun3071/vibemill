# Generator

> **Changelog v3:** Added the static analysis pass between verification and build. This enforces `ANTI_PATTERNS.md` rules 11 (no runtime data fetching) and 12 (no persistent storage) at the build pipeline level. See `SECURITY_ADDITIONS.md` for the SUSPICIOUS_PATTERNS additions. No other behavioral changes from v2.

> **Changelog v2:** Added the verification pass between generation and build. Added `verifier_verdict` and `verifier_notes` columns to apps schema (see `migrations/*/002_add_verifier_columns.sql`). Generator now produces two files (page_tsx, data_ts); README is a separate stage per `PERSONAS.md`. Added cross-reference to `ANTI_PATTERNS.md`.

The generator takes a prompt + a selected archetype and produces a deployable Next.js app. It uses DeepSeek V3 via OpenRouter.

## The chassis-and-slots model

Every archetype has a **chassis** (fixed scaffolding written by us, copied verbatim into every generated app of that archetype) and **slots** (files the LLM produces from a templated prompt).

The chassis includes:
- `package.json` with pinned dependencies (no HTTP clients, no databases, no scraping libs — see `SECURITY.md`)
- `tailwind.config.ts`
- `tsconfig.json`
- `.gitignore`
- `app/layout.tsx` (with the Vibe Mill footer disclaimer baked in)
- `lib/components/` (archetype-specific UI primitives)
- `public/favicon.ico` (the Vibe Mill mark)

The slots are produced by the LLM in two separate calls:
- **Generator call:** produces `app/page.tsx` and `lib/data.ts`
- **README call:** produces `README.md` (separate model call, separate prompt; see `PERSONAS.md`)

Slot files are written to disk after both calls succeed and the static analysis pass succeeds. Then chassis + slots are committed together as a single git repo and pushed.

## Why this architecture

**Output token economy.** A full Next.js app is 50k+ tokens to generate. Letting the LLM write only the slots (typically 5-15k tokens) cuts cost and latency significantly.

**Failure mode reduction.** The chassis files are pre-tested. If the LLM produces broken slot code, the build still has known-good infrastructure around it; the failure surface is smaller.

**Brand consistency.** The footer disclaimer, favicon, meta tags, and consistent Tailwind config come from the chassis. The LLM cannot accidentally remove the disclaimer.

**Separation of personas.** Generator writes code in service of the app. README writer writes in vibecoder voice. Keeping them separate prevents the personas from bleeding (see `PERSONAS.md`).

**Constraint enforcement.** The chassis pins `package.json` such that no forbidden dependencies (HTTP clients, databases, scraping libraries) are available at build time. Even if the generator hallucinates an import statement for a forbidden package, the build will fail because the package is not installed. This is defense-in-depth alongside the static analysis pass.

## Generator prompt template

The generator prompt is a Jinja-style template at `prompts/generator/{archetype}.txt`. For V0 the only one needed is `prompts/generator/tracker.txt`.

See `prompts/generator/tracker.txt` for the full text. The prompt produces a JSON object with `page_tsx` and `data_ts` keys.

The prompt explicitly instructs:
- *Bake all data into `lib/data.ts` as static TypeScript. Do not fetch external data at runtime.*
- *Do not import any database client, HTTP client, or scraping library.*
- *Do not use localStorage, sessionStorage, or cookies (exception: localStorage is permitted only for the Glorified to-do archetype).*

These constraints are also enforced at the static analysis layer.

### Variable substitution

The orchestrator substitutes `{{prompt}}`, `{{source_url}}`, `{{source_headline}}`, `{{source_summary}}` before sending to the LLM.

### Generator temperature

Run the generator at temperature **0.7**. Higher than the matcher (0.0) and guard (0.0). The higher temperature is deliberate per `ANTI_PATTERNS.md`: it produces confident, varied, sometimes-wrong outputs that are faithful to the vibecoding genre. Do not lower this.

## Verification pass

After the generator produces output and before the build runs, the orchestrator does a **single verification pass** with the same model. This stage exists because real vibecoders almost universally include a one-sentence "check it" prompt as part of their workflow. Vibe Mill reproduces this faithfully.

### The pipeline order

```
1. Generate          (deepseek-v3, t=0.7, archetype prompt)
   ↓
2. Verification pass (deepseek-v3, t=0.3, verifier prompt)
   ↓
3. Static analysis   (regex scan against SUSPICIOUS_PATTERNS; hard gate)
   ↓
4. Build check       (next build, technical correctness)
   ↓
5. Retry only on:    malformed JSON OR build failure
```

### The verifier prompt

Lives at `prompts/verifier.txt`. The full prompt is intentionally one sentence:

> *"Check if everything works. If you find issues, fix them and return the corrected files. If everything looks good, return the files unchanged."*

This prompt is **not to be improved**. See `ANTI_PATTERNS.md` rule 3. The shallowness is the point: it matches the median vibecoder's verification step exactly. An engineer-grade prompt would catch real bugs; vibe coders do not use engineer-grade prompts; Vibe Mill faithfully reproduces this.

### Verifier behavior

The verifier returns JSON with the same `page_tsx` / `data_ts` keys as the generator, plus:
- `verdict`: one of `"looks good"`, `"fixed issues"`, `"found issues but unsure how to fix"`
- `notes`: one to two sentences describing what was checked or fixed

The orchestrator handles the verdict as follows:

| Verdict | Behavior |
|---|---|
| `looks good` | Use the original generator output (verifier may have returned the files unchanged or with cosmetic edits; either is fine) |
| `fixed issues` | Use the verifier's edited files in place of the original |
| `found issues but unsure how to fix` | Use the original generator output anyway, ship the app |

**The verification pass is informational, not gating.** It cannot reject the app outright. It can only modify it. If the verifier's output is malformed JSON, retry once; on second failure, fall through with the original generator output unchanged.

### Logged fields

Every shipped app has these columns populated from the verifier:
- `verifier_verdict` (text): the verdict string
- `verifier_notes` (text): the notes string

These fields surface on the cemetery page (V1+). They are part of the public artifact. The verifier's "looks good" attestation alongside an actually-broken app is its own piece of satirical content.

### Verifier temperature

Run the verifier at temperature **0.3**. Lower than the generator (0.7) but not zero. Vibe coders running self-checks tend to use whatever Cursor or Claude Code defaults are, which are non-zero. Zero would over-discipline the verification.

## Static analysis pass

After verification and before the build, the orchestrator runs a regex scan on the slot files against `SUSPICIOUS_PATTERNS` (defined in `vibemill/security.py`, specified in `SECURITY.md` and `SECURITY_ADDITIONS.md`).

### What it enforces

- ANTI_PATTERNS rule 11: no runtime data fetching (catches `fetch`, `axios`, `httpx`, scraping libraries)
- ANTI_PATTERNS rule 12: no persistent storage (catches database clients, `sessionStorage`, cookie writes; conditional check for `localStorage` based on archetype)
- Pre-existing safety patterns (`eval`, `child_process`, etc.)

### Behavior

If any pattern matches:
- App is marked stillborn with `death_cause='forbidden_pattern'`
- The matched pattern and substring are logged for inspection
- No retry. The app does not ship.

This is the **only hard gate that reads code content**. The verifier is informational; the build check is structural; the static analysis is the policy gate.

### Why this is a separate stage

The static analysis is enforcement of project policy, not engineering quality. Mixing it with the verifier would conflict with `ANTI_PATTERNS.md` rule 3 (do not improve the verifier prompt). Mixing it with the build check would mean a forbidden pattern that happens to compile would slip through.

By making it its own stage, the policy is explicit and enforceable, and the verifier stays shallow as designed.

## Retry policy

The generator stage as a whole is allowed **one retry** on failure. The retry strategies are:

### Failure mode 1: malformed JSON output (generator)

The orchestrator parses the LLM response against a pydantic model. If parsing fails:
- Retry once with the malformed output appended to the prompt and an instruction: *"your previous output was not valid JSON. Fix it and respond again with valid JSON only."*
- If retry fails, ship as stillborn with `death_cause='never_built'`.

### Failure mode 2: malformed JSON output (verifier)

If the verifier produces malformed JSON:
- Retry once with the same prompt
- If retry fails, **fall through with the original generator output unchanged**, mark `verifier_verdict='verifier_failed'`
- This is not a stillbirth. The app still ships (subject to static analysis and build).

### Failure mode 3: forbidden pattern detected by static analysis

- Mark stillborn with `death_cause='forbidden_pattern'`
- Log the matched pattern and substring
- **No retry.** Forbidden patterns are policy violations, not transient errors.

### Failure mode 4: build failure

After writing slot files alongside the chassis, the orchestrator runs `next build` locally on sunfamily to verify the app compiles. If the build fails:
- Retry once. The retry re-runs *both* the generator and verifier with the build error appended to the generator prompt: *"your previous output produced a build error. Here is the error: ... Fix the issue."*
- The static analysis runs again on the retry output.
- If retry fails, ship as stillborn with `death_cause='never_built'`.

### Failure mode 5: build succeeds but app crashes at runtime

For V0, we do not test runtime behavior. If the app crashes when visited, that is on-brand and acceptable. Mark `screenshot_status='captured'` if a screenshot was obtained even if it shows an error page; mark `screenshot_status='missing'` if Playwright failed.

## Cost expectations

DeepSeek V3 via OpenRouter is approximately $0.27 per million output tokens. A typical Tracker generation:

- Generator input: ~3k tokens (prompt template + context)
- Generator output: ~6-12k tokens (two files)
- Verifier input: ~10k tokens (verifier prompt + generated files as context)
- Verifier output: ~6-12k tokens (returned files possibly modified)
- Cost per generation: $0.005 to $0.012 (generator + verifier combined)
- With one retry on average for ~30% of generations: $0.007 to $0.016 effective cost

Per-app total LLM cost (guard + matcher + generator + verifier + readme): under $0.10.

The static analysis pass adds zero LLM cost (regex only).

## Smoke test

The orchestrator must include a single end-to-end smoke test that exercises the full pipeline against a hardcoded "test news event" without touching production GitHub or Vercel. The test:

1. Loads a fixed test prompt
2. Runs guard (must pass)
3. Runs matcher (must select Tracker)
4. Runs generator
5. Runs verifier
6. Runs static analysis (must pass — the test prompt is designed to produce clean output)
7. Verifies all outputs are valid JSON
8. Writes files alongside the chassis
9. Runs `next build` in a temp directory
10. Asserts build succeeds

The test does NOT push to GitHub, deploy to Vercel, or take a screenshot. It exercises the LLM pipeline only.

Run via: `python -m vibemill.smoke_test`.

## See also

- `ANTI_PATTERNS.md` — rules about what NOT to improve. Especially rule 3 (verification prompt), rule 4 (calibration), rule 11 (no scraping), rule 12 (no persistence).
- `MATCHER.md` — guard and matcher stages preceding the generator.
- `PERSONAS.md` — the readme writer (a separate LLM call) uses different voice rules than the generator.
- `OPERATIONS.md` — how stillborn apps are recorded and surfaced.
- `SECURITY.md` + `SECURITY_ADDITIONS.md` — the SUSPICIOUS_PATTERNS list enforcing rules 11 and 12.
