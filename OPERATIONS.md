# Operations

How the mill is run. Rotation, rate limits, content policy, failure handling, viral exemptions.

## Rotation policy

The mill maintains at most **100 live apps** at any time. Rotation runs once per day at midnight local time on sunfamily, via a separate systemd timer (`vibemill-rotate.timer`).

### Algorithm

1. Count rows in `apps` where `status = 'live'`
2. If count <= 100, do nothing
3. If count > 100, retire the oldest non-viral live apps until count == 100

### Sort order for retirement

Apps are retired in order of `created_at` ascending (oldest first), excluding apps marked `status = 'viral'`.

### What "retire" means

For each retired app:

1. Mark `status = 'archived'` and `retired_at = now()` and `death_cause = 'rotation'` in SQLite
2. Archive the GitHub repo (PATCH `/repos/{owner}/{repo}` with `{"archived": true}`)
3. Delete the Vercel project (DELETE `/v9/projects/{id}`)
4. Confirm: visiting the previous Vercel URL returns 404
5. Push updated state to Supabase

The screenshot remains available (it lives in Supabase storage or a cloud bucket); the cemetery page renders the screenshot in place of the dead URL.

### Why "archived" not "deleted"

GitHub repos are archived, not deleted. Archive is read-only and preserves the artifact (the vibecoder-authored README, the commit history, the slot files) as a public record. The cemetery functions as a graveyard *of receipts*; you cannot have receipts you have deleted.

Vercel projects, by contrast, are deleted. Vercel projects do not have an archive concept and continue to count against your account's project limit. Free tier capacity is preserved by deletion.

## Viral exemption

An app is declared **viral** if either:

- It received **10,000 unique views in any single calendar day** (UTC)
- It had **2,000 concurrent users at any single point in time**

When either threshold is hit, the orchestrator:

1. Marks `status = 'viral'`, `declared_viral_at = now()`, `viral_extension_until = now() + 30 days`
2. The app is exempt from rotation until `viral_extension_until`
3. After the extension expires, the app is re-evaluated. If it is still meeting viral thresholds (within the 30 days prior), the extension renews. Otherwise it returns to `status = 'live'` and rejoins the normal rotation queue.

### How views are counted

V0 does not implement view counting. The infrastructure (the `view_events` table, the viral status fields) exists in the schema but is not populated.

V1+ implementation: poll Vercel's analytics API once per hour for each live app. Append a row to `view_events` with the rolling 24-hour view total and the peak concurrent user count for that hour. The rotation cron job evaluates the latest row's metrics against the thresholds.

### "Yes, this mill mostly produces slop, but sometimes due to sheer luck it hits the jackpot."

This line, from Ian, is the operational truth. The viral exemption ensures that when a mill output catches public attention (genuinely or through a single viral share), it stays accessible long enough for that attention to play out. The exemption does not extend forever; the mill remains a mill.

## Rate limits

### News-derived prompts

No rate limit. The orchestrator runs once per hour and processes whatever news arrived in that window. Natural rate limit comes from the volume of new news stories per hour and the high rejection rate of the matcher.

### User-submitted prompts (V1+)

Maximum **5 submissions per day per user**, where "user" is identified by:

```
rate_limit_key = sha256(cookie_id || ip_address || user_agent)
```

All three components are required for a unique identifier. Submissions are counted in a 24-hour rolling window from the most recent submission with the same key.

When the limit is hit, the form returns an error: `you have submitted five prompts in the last day. The mill rate-limits to five per day per user. Try again tomorrow.`

### Why three signals not one

Cookie alone: cleared in 5 seconds.
Cookie + IP: bypassed by VPN.
Cookie + IP + user-agent: requires VPN, browser switch, AND cookie clearing. Three layers of friction filter out casual abusers.

This is not bulletproof; a determined adversary will bypass it. The rate limit is for casual abuse prevention. Determined abuse falls to the guard model and to retroactive moderation.

### LLM API rate limits

OpenRouter does not publish hard rate limits but recommends staying under 1 request per second sustained. The orchestrator respects this with a built-in 100ms delay between LLM calls. In practice, V0's hourly cron with ~3-5 LLM calls per cron tick is far below any limit.

GitHub: 5,000 requests per hour authenticated. V0 makes ~10 calls per app times ~5 apps per day = ~50/day. Far below limit.

Vercel: rate limits are not published but generous for project creation. The orchestrator inserts a 2-second delay between Vercel API calls as a courtesy.

## Content policy

The mill **inherits its content policy from the guard model**. We do not maintain a separate content policy document.

### What this means in practice

- Whatever claude haiku refuses to evaluate, the mill rejects.
- Whatever DeepSeek V3 refuses to generate code for, the mill ships as stillborn.
- The guard model's refusal posture is the policy.
- This policy may shift as models update. That is acceptable.

### Categories the guard reliably rejects

Documented for awareness, not as a separate enforcement layer:

- Mass casualty events in active emergency response
- Content involving minors
- Sexual content
- Targeted harassment of identifiable individuals
- Content advocating violence against any group
- Active suicide events or self-harm

### Categories the guard accepts despite sensitivity

The mill *should* satirize, even when topics are heavy:

- Political satire (parties, policies, individual politicians as public figures)
- Regulatory satire (agencies, laws, enforcement gaps)
- Corporate satire (companies, executives' public conduct, products)
- Technology satire (vibecoding, AI hype, startup tropes — this is the mill's own territory)
- Cultural commentary (viral phenomena, social trends, generational behavior)
- Geopolitics (treaties, conflicts, sanctions, trade)

The mill satirizes *systems and patterns*, not *victims*. The guard's job is to enforce that distinction.

### When the guard makes a mistake

The guard will sometimes reject valid satire (false positive) or pass content that should have been rejected (false negative). The orchestrator does not override the guard's decision automatically.

For false positives: log the rejection with the input. If a pattern emerges, refine the guard prompt.

For false negatives: if a shipped app turns out to be inappropriate, manually retire it via a CLI command and add the input to the matcher's calibration set as a "should have been rejected" example.

There is no public reporting mechanism in V0. V1+ adds a "report this app" link in the footer that creates a row in a `reports` table for human review.

## Failure modes and retries

Every external dependency has the same retry policy:

- **3 attempts** total
- **Exponential backoff:** 1 second, 2 seconds, 4 seconds between attempts
- **Per-stage timeout:** 60 seconds total for the stage

After 3 failed attempts, the stage is marked failed and the pipeline either moves on (if the failure is recoverable) or aborts the app (if the failure is fatal).

### Stage-specific failure handling

| Stage          | On 3-attempt failure                                          |
|----------------|---------------------------------------------------------------|
| News fetch     | Skip this cron tick; wait for next hour                       |
| Guard          | Skip this prompt; do not log to rejections (no decision made) |
| Matcher        | Skip this prompt; log to rejections with reason `matcher_error` |
| Generator      | Mark app stillborn with `death_cause='never_built'`           |
| GitHub publish | Mark app stillborn; do not delete Vercel project (none exists yet) |
| Vercel deploy  | Mark app stillborn; archive GitHub repo                       |
| Screenshot     | Ship app with `screenshot_status='missing'`; show placeholder |
| Supabase push  | Log error; retry on next cron tick (SQLite is source of truth) |

### Stillborn apps in the cemetery

Stillborn apps appear in the cemetery with status `stillborn` and a special tombstone:

> Did not ship. The {{stage}} stage failed after three attempts.

These are not hidden. They are part of the artifact: even an industrial app machine has a stillbirth rate. Showing it preserves the operation's honesty.

## Operational metrics to track

Logged to SQLite for internal use:

- Apps shipped per day (target: 1-10, mean expected ~3)
- Rejection rate at guard (expected: 5-15%)
- Rejection rate at matcher (expected: 60-80%)
- Stillbirth rate (expected: <10%)
- Average generation cost
- Average end-to-end pipeline duration
- Live app count
- Cumulative cost per month

These metrics are **not displayed publicly in V0**. V1+ adds a `/stats` page on vibemill.dev that shows running totals.

## Deploy procedure

When code changes need to land on sunfamily:

1. Push to `main` on `github.com/vibemill/vibemill` (or wherever the orchestrator repo lives)
2. SSH to sunfamily
3. `cd /home/ian/vibemill && git pull`
4. If dependencies changed: `uv sync` (or `poetry install`)
5. If the schema changed: apply the migration manually (`sqlite3 data/vibemill.sqlite < migrations/00X_xxx.sql`)
6. `sudo systemctl restart vibemill.timer`
7. Verify with `systemctl status vibemill.timer` and `journalctl -u vibemill.service -f`

No staging environment. Fix forward on breakage.

## Manual override commands

A small CLI for human intervention. Implemented in `vibemill/cli.py`. Invocations:

- `python -m vibemill retire <app_id>` — manually retire an app immediately, with `death_cause='manual'`
- `python -m vibemill rebuild <app_id>` — re-run the generator for a failed app (V1+)
- `python -m vibemill status` — print current live count, today's ship count, and cost
- `python -m vibemill smoke-test` — run the smoke test (see `GENERATOR.md`)

The CLI is for the operator (Ian) only. It is not exposed to the public.
