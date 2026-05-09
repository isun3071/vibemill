# Security

Security and operational hygiene for Vibe Mill. Small project, but tokens leak fast and the satire fails if the operation behaves dishonestly.

## Threat model

What we are protecting against:

- **Token leakage.** Compromise of GitHub PAT, Vercel API token, OpenRouter key, or Supabase service role key gives an attacker the ability to spin up unauthorized resources, exhaust paid API credit, or delete the artifact corpus.
- **Supply chain attacks.** A malicious dependency update could introduce a backdoor, especially in a project that auto-deploys generated code.
- **Abuse of the generator.** Bad-faith user prompts (after V1) attempting to coax the LLM into producing malware, phishing pages, or harmful content.
- **Reputational compromise.** A shipped app that turns out to satirize tragedy badly, or to harass an individual, undermines the operation's honesty claim.

What we are not protecting against:

- Determined nation-state attackers. Out of scope.
- DDoS against vibemill.dev. Vercel and Cloudflare absorb this.
- Long-term archival integrity. Apps are ephemeral by design.

## Token inventory

All tokens are stored in `.env` files. There are two `.env` files: one on Ian's laptop (development), one on sunfamily (production). They are not synced; each machine has its own copy populated manually.

| Token                          | Where used                       | Rotation cadence | Scope                                |
|--------------------------------|----------------------------------|------------------|--------------------------------------|
| `OPENROUTER_API_KEY`           | guard, matcher, generator calls  | Every 6 months   | Account-wide                         |
| `GITHUB_TOKEN`                 | repo create/push/archive         | Every 90 days    | Fine-grained, scoped to vibemill-apps org |
| `VERCEL_TOKEN`                 | project create/deploy/delete     | Every 90 days    | Account-wide (no scoping option)     |
| `SUPABASE_URL`                 | snapshot push                    | N/A              | Public, not secret                   |
| `SUPABASE_SERVICE_ROLE_KEY`    | snapshot push                    | Every 90 days    | Bypasses RLS; treat as root          |
| `RESEND_API_KEY` (V1+)         | email send                       | Every 90 days    | Account-wide                         |

### `.env` template

The repo includes `.env.example` (committed) showing which env vars are needed. The actual `.env` (uncommitted) is populated locally.

```
# .env.example
OPENROUTER_API_KEY=
GITHUB_TOKEN=
GITHUB_ORG=vibemill-apps
VERCEL_TOKEN=
VERCEL_TEAM_ID=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
RESEND_API_KEY=

# Local config
SUNFAMILY_VIBEMILL_PATH=/home/ian/vibemill
SQLITE_PATH=/home/ian/vibemill/data/vibemill.sqlite
LOG_LEVEL=INFO
```

## No-commit list

The following must never be committed to git. The `.gitignore` enforces this:

```
.env
.env.local
.env.*.local
data/
*.sqlite
*.sqlite-journal
*.sqlite-wal
*.sqlite-shm
playwright-cache/
node_modules/
.next/
.vercel/
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
*.log
```

### Pre-commit hook

A pre-commit hook (`.git/hooks/pre-commit`, populated by `scripts/install-hooks.sh`) runs on every commit and:

1. Greps the staged diff for patterns that look like tokens (long random strings with high entropy)
2. Greps for known prefix patterns: `sk-`, `ghp_`, `github_pat_`, `vc_`, `eyJ` (JWT)
3. Aborts the commit if any match is found

The hook is not perfect; it is a backstop. The primary defense is the `.gitignore` and operator discipline.

## Token scoping

### GitHub

Use a **fine-grained personal access token** scoped to the `vibemill-apps` organization. Permissions:

- Repository permissions: Administration (read/write — needed to create and archive repos), Contents (read/write), Metadata (read)
- Organization permissions: none beyond the implicit org access

The token must NOT have access to Ian's personal repositories under `isun3071`. This isolation means a token leak compromises only the satirical artifact corpus, not Ian's real work.

### Vercel

Vercel tokens are account-wide; there is no team or project scoping in the standard API. To minimize blast radius, create a **dedicated Vercel team** for Vibe Mill if Vercel pricing permits, and scope the token to that team via `VERCEL_TEAM_ID`. If a separate team is not feasible, use the personal account but accept the broader scope.

### Supabase

Use the **service role key** for the orchestrator (not the anon key). The service role key bypasses Row Level Security. The orchestrator is the only entity that should hold this key. The Next.js public site uses the **anon key** for read operations; mode 2 form submissions go through a Next.js API route that holds the service role key server-side.

### OpenRouter

Account-wide. Set a hard spending cap in the OpenRouter dashboard (e.g., $50/month) so a leaked key cannot drain Ian's payment method.

## Generated code as an attack surface

The orchestrator runs `next build` against LLM-generated code. This is **executing untrusted code at build time**. While Next.js builds are sandboxed (no network access during build by default in modern Next.js), this is a real risk.

### Mitigations

- **Build in a temp directory** (`/tmp/vibemill-build-{uuid}`) that is deleted after the build completes
- **No environment variables exposed to the build.** The chassis does not consume any env vars at build time.
- **No filesystem access beyond the temp directory.** Run `next build` with reduced privileges if feasible (a dedicated unprivileged user; not implemented in V0 but considered for V1).
- **Static analysis check** before building: scan the generated code for suspicious patterns (`fetch(`, `eval(`, `child_process`, `fs.writeFile`). If found, mark the app stillborn rather than building. This filters out the LLM accidentally writing dangerous code without imposing burdensome sandboxing.

The static analysis check runs in `vibemill/security.py`, called by the orchestrator after the verifier and before the `next build` step. See `SECURITY_ADDITIONS.md` for the patch context. The full pattern list (also enforces `ANTI_PATTERNS.md` rules 11 and 12):

```python
SUSPICIOUS_PATTERNS_UNIVERSAL = (
    # Pre-existing safety
    r"\beval\s*\(",
    r"\bnew\s+Function\s*\(",
    r"\bchild_process\b",
    r"\bfs\.\w+",
    r"\brequire\s*\(\s*[\"']https?:",

    # Rule 11: runtime data fetching
    r"\bfetch\s*\(",
    r"\baxios\b",
    r"\bhttpx\b",
    r"\bgot\s*\(",
    r"\bnode-fetch\b",
    r"\bcheerio\b",
    r"\bjsdom\b",
    r"\bpuppeteer\b",
    r"\bplaywright\b",

    # Rule 12: persistent storage (database clients)
    r"\bpg\b",
    r"\bmysql2?\b",
    r"@supabase/supabase-js",
    r"@vercel/kv",
    r"@vercel/postgres",
    r"better-sqlite3",
    r"\bprisma\b",
    r"@planetscale/database",
    r"\bneon-database\b",
    r"@neondatabase/serverless",

    # Forbidden node APIs
    r"\bnet\.",
    r"\bdgram\.",
    r"\btls\.",
    r"\bcrypto\.subtle",

    # Rule 12: storage APIs forbidden in all archetypes
    r"\bsessionStorage\b",
    r"document\.cookie\s*=",
)
```

`localStorage` is permitted only in the `glorified_todo` archetype; the
`static_analysis(slot_files, archetype)` function applies this conditionally.

These patterns are NOT exhaustive; the goal is to catch the obvious cases
while keeping false positives low. On match: app is stillborn with
`death_cause='forbidden_pattern'`. No retry (per `GENERATOR.md` failure
mode 3).

## Supply chain

### Pinned dependencies

All Python dependencies are pinned in `pyproject.toml` with exact versions and locked transitively. All Next.js dependencies in the chassis are pinned the same way.

Bumps are deliberate: review changelogs before updating, run smoke test before deploying.

### Dependency review

When adding a new dependency, check:

- Is it well-maintained (last commit within 6 months)?
- Does it have a reasonable star/download count for its niche?
- Is the maintainer identifiable?
- Does it have known security advisories?

Use `pip-audit` (Python) and `npm audit` (Node) in CI if/when CI exists. Manually run before each deploy in V0.

## User input handling (V1+)

All user-submitted prompts:

1. Pass through the guard model
2. Are stored only with their `rate_limit_key` (a hash, not raw cookie/IP)
3. Are NOT echoed back to the submitter (to avoid using the form as an XSS vector if rendered)
4. Are sanitized for display on the public feed: HTML-escaped, length-limited to 280 characters

The form on the public site uses CSRF protection via Next.js's built-in `next/headers` request validation. No third-party CSRF library needed.

## Email handling (V1+)

Subscriber emails:

- Stored in Supabase `subscribers` table
- Each row has an `unsubscribe_token` (random UUID) generated at signup
- Unsubscribe link contains the token; clicking sets `unsubscribed_at = now()`
- Unsubscribed users are filtered out before any send
- Bounce handling: Resend webhook updates `bounced` and `bounce_count`; users with 3+ bounces are auto-unsubscribed

Subscriber list is **never sold, shared, or used for anything other than the milling notification**.

## Audit trail

Every state-changing operation logs:

- Timestamp (UTC)
- Operator (always 'orchestrator' for cron, 'cli' for manual interventions)
- Operation (e.g., `app.create`, `app.retire`, `app.viral_extend`)
- Target (app_id or other identifier)
- Reason (free text)

Audit log lives in `audit_log` table in SQLite, never deleted, never pushed to Supabase. This is for the operator's reconstruction of "what happened on day X" and not for public display.

## Incident response

If a token is suspected leaked:

1. Immediately rotate the token via the relevant provider's dashboard
2. Update `.env` on both laptop and sunfamily
3. Restart `vibemill.timer` on sunfamily
4. Audit recent activity in the relevant provider's dashboard for unauthorized actions
5. If unauthorized actions occurred (e.g., unauthorized repo creation), revert them manually

If a shipped app is found to be inappropriate:

1. `python -m vibemill retire <app_id>` to take it down
2. Add the input to the matcher calibration set
3. Refine the guard prompt if a pattern emerges

If a privacy concern is reported (e.g., a user's submitted prompt should not have been shipped publicly):

1. Manually retire the app
2. Delete the user's prompt from `user_submissions`
3. Apologize via email if contact info is available

## What we do not do

- We do not run telemetry or analytics on visitors beyond Vercel's defaults
- We do not sell, share, or correlate any user data
- We do not respond to data sales solicitations
- We do not comply with subpoenas without consulting counsel; the operator's contact info is in the about page

The operation's honesty is load-bearing for the satire. Behaving ethically is not optional.
