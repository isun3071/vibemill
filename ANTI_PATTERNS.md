# Anti-Patterns

> **Changelog v5:** Removed rules 11 (no runtime fetching), 12 (no persistent storage), and 13 (no parallel instances). 11 and 12 always sat awkwardly in this document — they were scope/safety constraints on generated apps, not "preserve faithfulness" rules — and removing them is consistent with the genre: real vibecoders DO wire up flaky `fetch()` calls and reach for `localStorage`. Rule 13 was operational, not satirical. Static analysis (`vibemill/security.py`) keeps the pre-existing safety patterns (`eval`, `child_process`, raw socket APIs, etc.) but no longer blocks fetch/storage.

> **Changelog v4:** Refined rules 1 and 5 in coordination. Rule 1 v4 allows reasoning where deliberately configured (DeepSeek V4 Flash at medium effort within the generator pool); the asymmetry across the pool is itself faithful to a real population of cost-conscious vibecoders. Rule 5 v4 distinguishes "do not filter to flatter the genre" (unchanged) from "DO sample across the variance space real human producers occupy" (new): single-pipeline LLM output is not the genre's natural distribution, so substrate rotation across the generator + README pool is faithfulness, not distribution-shaping. See `vibemill/model_rotation.py` and `OPERATIONS.md` "Generator substrate composition" for the implementation.

This document lists design choices that look like bugs, code smells, or "things to clean up later" — but are actually load-bearing for the project's purpose. They must not be improved.

## Why this document exists

Vibe Mill is a satirical existence proof. It demonstrates that ideation, conception, and execution of vibecoded portfolio artifacts can be fully automated. The demonstration only works if the artifacts vibe mill produces are *operationally indistinguishable* from artifacts that real vibecoders ship.

This means the failure modes that production AI applications work hard to suppress — hallucination, overconfidence, shallow self-verification, lack of grounding — are the exact properties that make vibecoded portfolios what they are. **Vibe Mill must not suppress these properties.** Suppressing them would make Vibe Mill cleaner than its target, which would defeat the satire.

When Claude Code (or any future contributor) reads this codebase and encounters something that looks improvable, the question to ask is: *would improving this make Vibe Mill less faithful to the vibecoding genre it satirizes?* If yes, do not improve it. The brokenness is part of the artifact.

## Principle: faithfully match, do not exceed

Vibe Mill's discipline is the discipline of *not adding discipline*. Every production-engineering instinct that says "make this better, more correct, more polished" is exactly what would defeat the satirical purpose.

The reference question is always: **"Does the median vibecoder do this?"** If yes, Vibe Mill does it. If no, Vibe Mill does not. Whether it would *improve* the artifact is irrelevant.

## The anti-patterns

### 1. Reasoning model use must be deliberate, not default (v4)

Reasoning-mode generator calls produce distinct fingerprints — longer "considered the trade-offs" prose, justified architecture choices, more elaborate commits — that ARE faithful to the genre. Real vibecoders turn on reasoning for the aesthetic of having thought things through, even when the underlying output remains slop.

Reasoning is allowed where deliberately configured. Current generator pool policy (see `vibemill/model_rotation.py` and `OPERATIONS.md`):

- **DeepSeek V4 Flash: reasoning at medium effort.** The model is cheap enough (~$0.84/M effective output at medium reasoning) that reasoning overhead stays well under the hard cap. Its strong SWE-bench performance produces the recognizable "I thought this through" fingerprint vibecoders perform.
- **All 7 other generator pool members: reasoning disabled.** Their effective costs at any non-zero reasoning effort would push past the hard cap (`MAX_OUTPUT_PRICE_USD_PER_M`).
- **Guard and matcher: reasoning disabled.** Fast classification, not deliberation.

The asymmetry is itself faithful: in a real population of vibecoders, only a subset turn reasoning on, and they tend to do so on the cheapest model that supports it (cost-conscious selection pressure). Vibe Mill's distribution mirrors this.

**If you find yourself wanting to enable reasoning across the whole pool "to fix the bug rate":** the bug rate is not a bug. It is the artifact. The reasoning-vs-fast asymmetry is itself fingerprint variance.

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

### 5. Do not filter to flatter the genre. DO sample real-producer variance. (v4)

**Don't filter the bad to make Vibe Mill look more competent than real slop.** The output of vibecoded slop is what it is — including broken builds, malformed JSON, embarrassingly bad copy. Some Vibe Mill apps will be visibly broken. Charts that render upside down. Date logic that fails for any year other than 2024. Dark mode toggles that delete user state on the second click. Maps with placeholder coordinates pointing to the middle of the Atlantic.

These apps are *the most representative*. Filtering them out would skew the public output toward the misleading "well, vibecoded apps usually work fine" claim that real vibecoders make to defend themselves. The visibly broken ones are the receipts.

**Ship them. Do not retry. Do not hide.**

The only outputs that should be excluded are those that fail the build entirely (compile errors after one retry) or fail the static security scan (`SUSPICIOUS_PATTERNS` in `SECURITY.md`). Everything else ships.

**AND: faithful representation of the genre includes fingerprint-level variance.** Real vibecoders leave individual marks via different tools, palettes, layouts, copy registers, and small idiosyncratic choices. Two humans producing structurally-identical Trackers for the same news headline would not converge on identical UI down to the pixel — they'd differ in palette flavor, copy tics, small idiosyncratic choices.

Single-pipeline LLM output (one model, one temperature, one prompt) produces zero fingerprint variance. That is not the genre's natural distribution; the genre's natural distribution is across thousands of human producers using different tools.

Sampling across the variance space real human producers occupy is **faithfulness, not distribution-shaping.**

The distinction:
- **Don't filter to remove the bad.** A broken Tracker ships.
- **DO sample across substrate variance.** Generator + README rotate through a configured pool (`vibemill/model_rotation.py`) so the corpus carries fingerprint marks of multiple substrates, mirroring the multi-tool reality of the producer population the satire targets.

Prompt-side variance dimensions (palette, layout primitive, copy register, header style) are deferred to a later session — they're a different change.

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



## A reminder about the project's identity

Vibe Mill is not an engineering exercise that happens to be satirical. It is a satirical existence proof that happens to require some engineering. Treat the engineering as *in service of* the satire, not the other way around.

When the engineering instinct conflicts with the satirical purpose, the satire wins. Always.
