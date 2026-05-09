# Security additions (v2)

> **Purpose:** This is a patch document. It specifies the additions to `SECURITY.md` that enforce `ANTI_PATTERNS.md` rules 11 (no scraping/runtime data fetching) and 12 (no persistent storage in generated apps) at the static analysis layer. Apply these to the existing `SUSPICIOUS_PATTERNS` list in `SECURITY.md`.

## Context

Generated apps that contain forbidden patterns are marked stillborn at the static analysis stage, before deployment. The verifier may attempt to fix forbidden patterns (which is fine — the verifier moving in the right direction is acceptable). The static analysis is the hard gate. Anything that survives the verifier and still has forbidden patterns is rejected.

## SUSPICIOUS_PATTERNS additions

Add the following regex patterns to the existing `SUSPICIOUS_PATTERNS` list in `vibemill/security.py` (or wherever the list lives in code). The existing patterns (`eval`, `new Function`, `child_process`, `fs.*`, `require('https?:')`, `fetch(...${`) are preserved.

### Runtime data fetching (enforces Rule 11)

```python
# Generic fetch — any fetch in generated apps is suspicious because data
# must be baked in at build time
r"\bfetch\s*\(",

# HTTP clients
r"\baxios\b",
r"\bhttpx\b",  # defensive; shouldn't appear in TS
r"\bgot\s*\(",  # got is a node http client
r"\bnode-fetch\b",

# Scraping libraries
r"\bcheerio\b",
r"\bjsdom\b",
r"\bpuppeteer\b",
r"\bplaywright\b",  # generated apps don't run playwright; vibe mill does
```

### Persistent storage (enforces Rule 12)

```python
# Database clients
r"\bpg\b",  # postgres
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
r"\bnet\.",  # net module
r"\bdgram\.",  # UDP
r"\btls\.",  # TLS module
r"\bcrypto\.subtle",  # potentially worrying patterns
```

### Storage APIs (Rule 12 — clarification)

`localStorage` is permitted *only* for the Glorified to-do archetype. The static analysis cannot easily distinguish archetypes at the file level, so:

- `localStorage` use is detected but **gates only on archetype**. The orchestrator passes the archetype name to the static analysis function. If `archetype != "glorified_todo"` and `localStorage` appears in the slot files, the app is stillborn.
- `sessionStorage` is forbidden in all archetypes. Add a hard pattern.
- `cookie` setting (e.g. `document.cookie =`, `Set-Cookie` header writes) is forbidden in all archetypes.

```python
# sessionStorage is forbidden in all archetypes
r"\bsessionStorage\b",

# Cookie setting (read is harder to gate; setting is forbidden)
r"document\.cookie\s*=",
```

The orchestrator's static analysis function should accept the archetype name and apply the localStorage check conditionally:

```python
def static_analysis(slot_files: dict[str, str], archetype: str) -> tuple[bool, str | None]:
    """
    Returns (is_safe, reason_if_not).
    """
    combined = "\n".join(slot_files.values())

    # Universal patterns
    for pattern in SUSPICIOUS_PATTERNS_UNIVERSAL:
        if re.search(pattern, combined):
            return False, f"matched universal forbidden pattern: {pattern}"

    # localStorage is permitted only for glorified_todo
    if archetype != "glorified_todo":
        if re.search(r"\blocalStorage\b", combined):
            return False, "localStorage used outside glorified_todo archetype"

    return True, None
```

## Order of operations in the build pipeline

1. **Generator** writes code (might include forbidden patterns due to hallucination)
2. **Verifier** passes (might keep forbidden patterns, might fix them — informational, not gating)
3. **Static analysis check** (hard fail on forbidden patterns; this is the safety net)
4. **Build check** (`next build`; hard fail on compile errors)

If static analysis fails after the verifier pass, the app is stillborn with `death_cause='forbidden_pattern'`. The specific pattern and matched substring are logged for inspection. This is rare in practice — the generator prompts already instruct against external data and persistence — but the check is the safety net.

## What this document does not change

- The verifier prompt is not modified. Per `ANTI_PATTERNS.md` rule 3, the verifier prompt stays at one sentence. The verifier might happen to fix forbidden patterns (which is fine), but it is not asked to specifically check for them.
- The generator prompts (`prompts/generator/*.txt`) already say "do not fetch external data; the data is baked in at build time." Verify this constraint is in all archetype prompts before they are added.
- The chassis files (`package.json`, `tailwind.config.ts`, etc.) do not import any forbidden libraries. Pinned dependencies in the chassis are: `next`, `react`, `react-dom`, `tailwindcss`, `typescript`, `@types/node`, `@types/react`, plus archetype-specific UI libraries (chart.js for chart-using archetypes, lucide-react for icons). Nothing else.

## Apply these changes

When integrating into the existing `SECURITY.md`:

1. Append the new patterns to the existing `SUSPICIOUS_PATTERNS` list (or split into `SUSPICIOUS_PATTERNS_UNIVERSAL` and conditional checks)
2. Update the static analysis function signature to accept `archetype: str`
3. Update the orchestrator call site to pass the archetype
4. Add `forbidden_pattern` as a possible value for `death_cause` in the apps schema (already covered by the existing column type, no migration needed)
5. Reference `ANTI_PATTERNS.md` rules 11 and 12 in the relevant section header in `SECURITY.md` so future readers know where the policy comes from
