# Anti-Patterns

> **Changelog v3:** Added rules 11 (no scraping or runtime data fetching), 12 (no persistent storage in generated apps), and 13 (do not scale Vibe Mill to multiple instances). Updated reference to `SECURITY.md` for the static analysis enforcement of rules 11 and 12.

This document lists design choices that look like bugs, code smells, or "things to clean up later" — but are actually load-bearing for the project's purpose. They must not be improved.

## Why this document exists

Vibe Mill is a satirical existence proof. It demonstrates that ideation, conception, and execution of vibecoded portfolio artifacts can be fully automated. The demonstration only works if the artifacts vibe mill produces are *operationally indistinguishable* from artifacts that real vibecoders ship.

This means the failure modes that production AI applications work hard to suppress — hallucination, overconfidence, shallow self-verification, lack of grounding — are the exact properties that make vibecoded portfolios what they are. **Vibe Mill must not suppress these properties.** Suppressing them would make Vibe Mill cleaner than its target, which would defeat the satire.

When Claude Code (or any future contributor) reads this codebase and encounters something that looks improvable, the question to ask is: *would improving this make Vibe Mill less faithful to the vibecoding genre it satirizes?* If yes, do not improve it. The brokenness is part of the artifact.

## Principle: faithfully match, do not exceed

Vibe Mill's discipline is the discipline of *not adding discipline*. Every production-engineering instinct that says "make this better, more correct, more polished" is exactly what would defeat the satirical purpose.

The reference question is always: **"Does the median vibecoder do this?"** If yes, Vibe Mill does it. If no, Vibe Mill does not. Whether it would *improve* the artifact is irrelevant.

## The anti-patterns

### 1. Do not use reasoning models for codegen

Reasoning models (o1, o3, deepseek-r1, gpt-5-thinking, claude with extended thinking, etc.) slow down, think step-by-step, double-check their outputs, and produce measurably more correct code.

This is exactly wrong for Vibe Mill. The cheap, fast, non-reasoning model (DeepSeek V3 chat) is correct. The lack of reasoning is a feature: it produces the same kind of one-shot output a vibecoder gets when they prompt Cursor on temperature 0.7.

**If you find yourself wanting to switch to a reasoning model "to fix the bug rate":** the bug rate is not a bug. It is the artifact.

### 2. Do not add hallucination suppression

Hallucination in code generation manifests as fabricated APIs, plausible-but-wrong logic, misremembered library behavior, imagined data shape, and inconsistent internal state. In normal applications, every one of these is a defect.

In Vibe Mill, hallucinated outputs are *empirically calibrated* to what real vibecoded portfolios actually look like. A Vibe Mill that produced clean code would be *less honest* about the genre.

**Do not add:**
- RAG or grounded generation that forces the LLM to actually know things
- Tool-calling for fact verification (e.g., search-API checks against the news source)
- Citation requirements that prevent fabrication
- Schema validators that catch hallucinated API surfaces

### 3. Do not improve the verification prompt

The verification stage in `GENERATOR.md` uses a deliberately shallow one-sentence prompt: *"Check if everything works."*

This is not laziness. It is the *exact* prompt the median vibecoder uses. An engineer-grade verification prompt would catch real bugs. That prompt is engineering. Vibe coders do not use that prompt. So Vibe Mill does not use it either.

**Do not:**
- Replace the verifier prompt with a more rigorous one
- Add a second verification pass (cascading verifiers)
- Run the verifier under a reasoning model
- Add CI/CD-style automated checks (eslint, typecheck, test runs) as part of the verification stage

The build check (`next build`) is the only technical correctness gate. Everything else is a vibe check.

### 4. Do not calibrate confidence

Overconfidence in LLMs manifests as: picking one interpretation of an ambiguous prompt without flagging the ambiguity; fabricating specifics in summaries; harmonizing inconsistent inputs; rejecting uncertainty in hedged ranges; filling gaps with plausible content.

In normal applications these are calibration failures. In Vibe Mill, they are *what makes the apps look like real products*. A hedged, well-calibrated LLM would write copy that looks like a research draft. Vibe Mill's apps need to look like products. The overconfidence is what produces the visual signature of "this looks like a real product."

**Do not:**
- Lower temperature below the default for the generator (the matcher and guard use temperature 0; the generator should run higher, ~0.7)
- Add hedging instructions to the generator prompt ("flag uncertainty", "note when data is incomplete")
- Add a calibration pass that softens overconfident claims

### 5. Do not filter the bad outputs

Some Vibe Mill apps will be visibly broken. Charts that render upside down. Date logic that fails for any year other than 2024. Dark mode toggles that delete user state on the second click. Maps with placeholder coordinates pointing to the middle of the Atlantic.

These apps are *the most representative*. Filtering them out would skew the public output toward the misleading "well, vibecoded apps usually work fine" claim that real vibecoders make to defend themselves. The visibly broken ones are the receipts.

**Ship them. Document the bug on the cemetery card. Do not retry. Do not hide.**

The only outputs that should be excluded are those that fail the build entirely (compile errors after one retry) or fail the static security scan (`SUSPICIOUS_PATTERNS` in `SECURITY.md`). Everything else ships.

### 6. Do not add post-deployment monitoring or alerting

It is tempting to add error tracking (Sentry, Bugsnag) to generated apps so that runtime crashes get reported. Do not. A vibecoded portfolio piece does not have observability. Vibe Mill's apps must not either.

The user visiting a Vibe Mill app and seeing it crash is a feature. The crash is the gap between surface-quality and substance-quality, materially demonstrated. Telling the operator about the crash so they can fix it would defeat the demonstration.

**The cemetery is the only post-deployment record.** Apps die on schedule, archived with whatever bugs they had at end of life. No remediation.

### 7. Do not "fix" the readme persona

Generated READMEs (per `PERSONAS.md`) are written from a vibecoder persona: enthusiastic, emoji-laden, with subtle tells in the closing paragraph that reveal the machine origin. The tells include syntactic over-uniformity, self-praise that overshoots, generic "About the developer" sections, and the "Future Work" list ending with a self-aware joke.

Future Claude Code may want to "tighten" these READMEs because they read as obviously AI-generated. **Do not.** They are obviously AI-generated *because they are AI-generated*. The persona is faithful to the genre, including the tells. Improving the persona to read more human would be the satirical equivalent of teaching the bot to lie better.

The same applies to fake commit histories: the progressive shift from "initial commit" to "i don't know what this code does" is part of the bit. Do not normalize the messages.

### 8. Do not introduce abstractions speculatively

Vibe Mill has 12 archetypes. They are 12 templates, not 12 instances of an abstract pattern. If you find yourself writing a `BaseArchetype` class with `_generate_slots()` hooks, stop. The archetypes are different in shape and the abstraction would impose false uniformity.

This rule is general — applies throughout the codebase — but it is especially load-bearing for the archetype layer because the *concept* of an archetype library is satirically meaningful. A factory has SKUs. SKUs are not instances of a metaclass. They are units of inventory.

### 9. Do not optimize for cost beyond the daily cap

The daily cost cap (`DAILY_COST_CAP_USD` in `.env`) is the hard limit. Within that limit, do not optimize further. Do not cache LLM outputs across requests. Do not reuse generated code across apps "to save tokens." Do not batch generations to amortize overhead.

Each app is a fresh artifact, generated independently. Optimization of inference cost would create artifact homogeneity that vibecoded portfolios do not have. The variation between apps — including expensive variation — is what makes the cemetery look like a real graveyard rather than a content farm.

### 10. Do not advertise the satire

The mill does not announce itself as a satire. The about page describes what the mill does, factually. The disclaimer in each app says it was generated by Vibe Mill, factually. The cemetery shows lifespan and cost, factually. **The reader concludes the satire on their own.**

Do not add:
- "This project is satire" anywhere in user-facing copy
- Self-deprecating jokes about being a satire
- Meta-commentary about the project's purpose in any user-facing copy
- Apologetic disclaimers ("we know this looks bad, that's the point")

`THESIS.md` is the exception: it is *for* explaining the satire, because it lives outside the user-facing surface. Linking to THESIS.md from the about page is fine. Quoting THESIS.md *into* the about page is not.

The satire's effectiveness depends on the reader recognizing it without being told. Telling them ruins it.

### 11. Do not scrape, fetch, or otherwise pull external data at runtime

Generated apps must have all their data baked in at build time as static TypeScript. The LLM produces the data values when it generates the slot files. The values are fabricated, possibly wrong, and never updated after deployment.

This is canonical and load-bearing for several reasons:

- **Real vibecoded apps are full of hallucinated data.** A Tracker app with "47 confirmed cases reported" and no source citation is the standard genre artifact. Vibe Mill must match this fidelity. Apps that scraped real data would be cleaner than the genre they satirize, defeating the demonstration.
- **The verifier "looks good" attestation alongside fabricated numbers is its own piece of satirical content.** The dashboard says 47. The verifier signed off on 47. The actual figure is unknown or different. *That is the artifact.*
- **Scraping breaks the rotation policy.** Archived apps cannot continue scraping. Live apps that scrape can break when sites change. Apps deployed to Vercel share IP pools that get blocked.
- **The cost model assumes static deployments.** Persistence introduces operational and financial categories outside the cap.
- **The audience visits Vibe Mill apps to see what the mill produces, not to consume accurate data.** Real data would actually weaken the artifact.

Generated apps must therefore not import any HTTP client (`httpx`, `fetch`, `axios`), any scraping library (`BeautifulSoup`, `Cheerio`, `Playwright`), or call any external API at runtime. All data is hallucinated by the LLM at build time and frozen into the bundle.

This rule is enforced by the static analysis pass (`SUSPICIOUS_PATTERNS` in `SECURITY.md`).

**One narrow exception:** archetypes that need a static entity pool larger than typical slot data (Wordle redux of senators, recommendation engines over a domain space) may have larger hallucinated entity lists baked into static data files. They still do not fetch at runtime. The LLM hallucinates the entities at build time; the artifact ships frozen.

### 12. Do not give generated apps persistent storage

Generated apps must not have backing databases, persistent server state, or any storage that survives across visits, deploys, or users.

Permitted:
- Static data baked into TypeScript at build time
- React in-memory state (`useState`, `useReducer`) that resets on refresh
- URL query params for shareable views
- `localStorage` *only for the Glorified to-do archetype*, with check-off state local to the user's browser

Forbidden:
- Vercel KV, Vercel Postgres, Supabase, PlanetScale, Neon, or any external database
- SQLite shipped with the app and written at runtime
- API routes that write to any persistent store
- Cookies for application state

Reasons:

- **Persistence implies users.** Users imply moderation, privacy, and abuse surface that contradicts the satirical artifact factory scope. The moment any app accepts and persists user content, Vibe Mill has accepted operational responsibilities the project cannot carry.
- **The rotation policy requires apps to be frozen at deploy time.** Databases break the frozen-snapshot model. The screenshot taken at archive time must accurately represent the app's state forever.
- **The median vibecoded portfolio piece does not have real persistence either.** It has mock data and broken save buttons. Vibe Mill matches this fidelity faithfully.
- **The cost model assumes apps are static deployments.** Persistence introduces operational costs outside the cap.

Generated apps that *look like* they save state should fail to actually save it on refresh. This is on-brand. The user clicking the heart icon, seeing the count go up, refreshing, and seeing it reset — that is the artifact. Vibecoded portfolios pretend to have working features; real users clicking around find the buttons don't actually save anything; Vibe Mill ships exactly this experience faithfully.

This rule is also enforced by the static analysis pass (`SUSPICIOUS_PATTERNS` in `SECURITY.md`).

### 13. Do not scale Vibe Mill to multiple parallel instances

The satirical claim of Vibe Mill is structurally complete at one instance. Scaling to multiple instances would defeat the project for several converging reasons.

**It would convert the project from satirical demonstration to operational AI app farm.** Audiences have already filed away "AI app farm" as a category and stopped finding it interesting. The bit becomes "yet another AI slop generator at scale" instead of "a single hobbyist demonstrates structural breakage."

**It would require evading platform abuse-detection.** Vercel free-tier hobby allowances assume non-commercial single-operator use. Fifty parallel instances is not plausibly that. GitHub abuse-detection flags rapid org-creation patterns. OpenRouter dashboards make multi-account inference patterns visible. Evading these systems would contradict the load-bearing claim that *Vibe Mill runs on $5/month with no maintenance*.

**It would externalize real costs for fixed satirical output.** Fifty instances consume fifty times the LLM compute, with real environmental footprint, real infrastructure noise, real risk of contributing to the slop substrate Vibe Mill satirizes (training-data contamination). The satirical content produced does not scale; the externalities do.

**It would remove the audience's extrapolation moment.** The math is the rhetorical asset. *"To match the entire global college hackathon ecosystem for $4,800/year"* is unforgettable as a thought experiment. Running 60 instances yourself does the multiplication for the audience and replaces the realization with a less-interesting fact.

**It would defeat Pillar 1's structural integrity.** Vibe Mill at one instance is the satirical artifact. Vibe Mill at fifty instances is what the satire warns about. The operating principle is *"this is mechanically reproducible by anyone with $5-20/month"*. One instance demonstrates this. Fifty instances would be exploiting it.

The threat is the demonstration. Running the threat would deflate it. The discipline to stay at one instance is part of what distinguishes Vibe Mill from the thing it depicts.

If the demonstration appears to need scaling to land, the satire has failed for non-scaling reasons that cannot be fixed by scaling.

## How to handle the urge to improve

When you encounter something in this codebase that looks improvable, follow this checklist:

1. **Is the thing in question something the median vibecoder does?** If yes: it stays. If no, continue.
2. **Would improving it make Vibe Mill faster, cheaper, or more reliable in a way that does not change what the artifacts look like?** If yes: improve it. If no, continue.
3. **Would improving it change the *look* or *feel* of the generated apps?** If yes: do not improve it.
4. **Would improving it make Vibe Mill *cleaner than the genre it satirizes*?** If yes: do not improve it. The brokenness is the receipt.

If after running this checklist you are still unsure: **stop and ask the user.** Drift toward "make it better" is the most predictable failure mode for any contributor working on this project, including LLM contributors. Surface the call rather than make it silently.

## A reminder about the project's identity

Vibe Mill is not an engineering exercise that happens to be satirical. It is a satirical existence proof that happens to require some engineering. Treat the engineering as *in service of* the satire, not the other way around.

When the engineering instinct conflicts with the satirical purpose, the satire wins. Always.
