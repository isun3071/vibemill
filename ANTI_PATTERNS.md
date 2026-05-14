# Anti-Patterns

> **Changelog v6:** Rule 5 → v5 (variance lives at the prompt layer, not substrate). Substrate rotation across the 8-model generator pool is gone; the corpus runs on a single substrate (DeepSeek V4 Flash, reasoning effort driven by tier). Empirically, substrate rotation was reading as fingerprint *noise* rather than fingerprint *variance* — outputs looked similar regardless of which model produced them because the prompt was the binding constraint. Layout-archetype rotation (Bundle C), tier-driven effort (Bundle A), upcoming archetype expansion (planned Bundle F), upcoming sub-prize-category and track conditioning (planned Bundle G), and README persona rotation (still in force) are where the visible variance now lives. Single substrate is also arguably MORE faithful to any individual hackathon team's behavior (no team rotates 8 models). Rule 1 simplifies in turn: reasoning is tier-driven (slop disabled, mean_good low, banger medium), not pool-asymmetric.

> **Changelog v5:** Removed rules 11 (no runtime fetching), 12 (no persistent storage), and 13 (no parallel instances). 11 and 12 always sat awkwardly in this document — they were scope/safety constraints on generated apps, not "preserve faithfulness" rules — and removing them is consistent with the genre: real vibecoders DO wire up flaky `fetch()` calls and reach for `localStorage`. Rule 13 was operational, not satirical. Static analysis (`vibemill/security.py`) keeps the pre-existing safety patterns (`eval`, `child_process`, raw socket APIs, etc.) but no longer blocks fetch/storage.

> **Changelog v4:** Refined rules 1 and 5 in coordination. Rule 1 v4 allowed reasoning where deliberately configured (DeepSeek V4 Flash at medium effort within the generator pool); the asymmetry across the pool was itself faithful to a real population of cost-conscious vibecoders. Rule 5 v4 distinguished "do not filter to flatter the genre" (unchanged) from "DO sample across the variance space real human producers occupy" (the substrate-rotation argument). **Superseded by v5/v6** — see above.

This document lists design choices that look like bugs, code smells, or "things to clean up later" — but are actually load-bearing for the project's purpose. They must not be improved.

## Why this document exists

Vibe Mill is a satirical existence proof. It demonstrates that ideation, conception, and execution of vibecoded portfolio artifacts can be fully automated. The demonstration only works if the artifacts vibe mill produces are *operationally indistinguishable* from artifacts that real vibecoders ship.

This means the failure modes that production AI applications work hard to suppress — hallucination, overconfidence, shallow self-verification, lack of grounding — are the exact properties that make vibecoded portfolios what they are. **Vibe Mill must not suppress these properties.** Suppressing them would make Vibe Mill cleaner than its target, which would defeat the satire.

When Claude Code (or any future contributor) reads this codebase and encounters something that looks improvable, the question to ask is: *would improving this make Vibe Mill less faithful to the vibecoding genre it satirizes?* If yes, do not improve it. The brokenness is part of the artifact.

## Principle: faithfully match, do not exceed

Vibe Mill's discipline is the discipline of *not adding discipline*. Every production-engineering instinct that says "make this better, more correct, more polished" is exactly what would defeat the satirical purpose.

The reference question is always: **"Does the median vibecoder do this?"** If yes, Vibe Mill does it. If no, Vibe Mill does not. Whether it would *improve* the artifact is irrelevant.

## The anti-patterns

### 1. Reasoning model use is tier-driven, not default (v5)

Reasoning-mode generator calls produce distinct fingerprints — longer "considered the trade-offs" prose, justified architecture choices, more elaborate commits — that ARE faithful to the genre. Real vibecoders turn on reasoning for the aesthetic of having thought things through, even when the underlying output remains slop.

Reasoning is tier-driven (see `vibemill/model_rotation.py`):

- **Slop tier (~10%): reasoning disabled.** The vibecoder running on fumes at 3am isn't turning on reasoning. Cheapest, fastest, sloppiest.
- **Mean_good tier (~82%): reasoning LOW.** A touch of reasoning for cross-file coherence — the sub-prize-winning team thought a *little* about it. Effective output ~$0.42/M.
- **Banger tier (~8%): reasoning MEDIUM.** The committed-QA team actually deliberates. Effective output ~$0.84/M.
- **Guard and matcher: reasoning disabled.** Fast classification, not deliberation.

The per-tier asymmetry is itself faithful: in a real population of vibecoders, the half-assing cohort doesn't toggle reasoning; the polishing cohort does. Vibe Mill mirrors that.

**If you find yourself wanting to enable reasoning across all tiers "to fix the bug rate":** the bug rate is not a bug. It is the artifact. The tier-vs-tier asymmetry IS fingerprint variance — and so is the difference between a reasoning-on banger and a reasoning-off slop.

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

### 5. Do not filter to flatter the genre. DO sample variance at the prompt layer. (v5)

**Don't filter the bad to make Vibe Mill look more competent than real slop.** The output of vibecoded slop is what it is — including broken builds, malformed JSON, embarrassingly bad copy. Some Vibe Mill apps will be visibly broken. Charts that render upside down. Date logic that fails for any year other than 2024. Dark mode toggles that delete user state on the second click. Maps with placeholder coordinates pointing to the middle of the Atlantic.

These apps are *the most representative*. Filtering them out would skew the public output toward the misleading "well, vibecoded apps usually work fine" claim that real vibecoders make to defend themselves. The visibly broken ones are the receipts.

**Ship them. Do not retry. Do not hide.**

The only outputs that should be excluded are those that fail the build entirely (compile errors after the tier's retry budget) or fail the static security scan (`SUSPICIOUS_PATTERNS` in `SECURITY.md`). Everything else ships.

**AND: faithful representation of the genre includes visible variance — but variance lives at the PROMPT LAYER, not at substrate rotation.**

Bundle E (this codebase, May 2026) abandoned substrate rotation after v4's hypothesis didn't pay out empirically. Substrate variance across 8 different LLMs was producing *fingerprint noise*, not *fingerprint variance* — outputs looked structurally similar regardless of which model wrote them because the prompt was the binding constraint. Real human producers DO use different tools, but no individual team rotates 8 tools per project. A single team's behavior is single-substrate; the across-team variance lives in *what they choose to build* and *how they structure it*, not in *which LLM they typed at*.

So Vibe Mill's variance lives at the prompt layer now:
- **Tier rotation** (`vibemill/tiers.py`) — three effort levels (slop / sub-prize-winner / banger) with different search, retry, reasoning budgets
- **Layout-archetype rotation within Tracker** (`vibemill/layouts.py`, Bundle C) — 8 structural layouts (dashboard / long_form / map / chart / editorial / card_feed / list / split_view)
- **Archetype rotation** (planned Bundle F) — incremental expansion of the buildable archetype set
- **Track conditioning + sub-prize category** (planned Bundle G) — hackathon-track-derived idea scoping and per-app polish-axis sampling
- **README persona rotation** (`vibemill/readme_writer.py`) — voice variance via 12 distinct README personas; orthogonal to everything else

Single substrate (DeepSeek V4 Flash) carries all of it. Cheap enough to support the prompt-layer expansion, capable enough to render any of the above.

### 6. Do not add post-deployment monitoring or alerting

It is tempting to add error tracking (Sentry, Bugsnag) to generated apps so that runtime crashes get reported. Do not. A vibecoded portfolio piece does not have observability. Vibe Mill's apps must not either.

The user visiting a Vibe Mill app and seeing it crash is a feature. The crash is the gap between surface-quality and substance-quality, materially demonstrated. Telling the operator about the crash so they can fix it would defeat the demonstration.

**The cemetery is the only post-deployment record.** Apps die on schedule, archived with whatever bugs they had at end of life. No remediation.

### 7. Do not "fix" the readme persona

Generated READMEs (per `PERSONAS.md`) are written from a vibecoder persona: enthusiastic, emoji-laden, with subtle tells in the closing paragraph that reveal the machine origin. The tells include syntactic over-uniformity, self-praise that overshoots, generic "About the developer" sections, and the "Future Work" list ending with a self-aware joke.

Future Claude Code may want to "tighten" these READMEs because they read as obviously AI-generated. **Do not.** They are obviously AI-generated *because they are AI-generated*. The persona is faithful to the genre, including the tells. Improving the persona to read more human would be the satirical equivalent of teaching the bot to lie better.

The same applies to fake commit histories: the progressive shift from "initial commit" to "i don't know what this code does" is part of the bit. Do not normalize the messages.

The same applies to **disproportionate setup rituals**: a slop-tier Flask app whose README contains a 12-step Google Cloud Console OAuth walkthrough for an auth flow the code barely implements is not a tier violation — it is the most genre-authentic artifact the mill produces. Abandoned hackathon repos have setup docs longer than their source files. The disproportion between ritual and function is the joke. Do not add "slop README must not mention OAuth" guards.

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

### 11. The moves that convert Vibe Mill into a fork, not an improvement

`THESIS.md` predicts two appropriation forks: **Vibe Mill 2.0** (commercial SaaS-slop mill, profit-seeking) and **Vibe Mill 1.0P** (personalized portfolio mill, credentialing-fraud-seeking). The two forks share an enabling substrate but operate on different harm surfaces. Naming them here, in detail, is part of the first-mover frame-setting: any reader of this file who performs the moves below is doing something the satirical original has already named as the line. The fork can still happen. The fork cannot pretend to be innocent.

**Fork A — Vibe Mill 2.0 (commercial appropriation).** The following moves convert the mill into a profit-seeking SaaS factory:
- Removing the cemetery (apps stop dying on schedule; they accumulate as products)
- Removing the disclaimer (artifacts stop disclosing machine origin)
- Removing the rotation (the artifact pile becomes a permanent catalog instead of evidence)
- Sanitizing the verifier output (verifier verdicts become marketing copy rather than ironic content)
- Removing the cost ledger (the cost-asymmetry argument disappears with the data behind it)
- Adding post-deployment monitoring or alerting (the indifference posture flips to product-care; see rule 6)
- Adding hallucination suppression (the genre-faithful overconfidence is replaced with reliability; see rule 2)
- Wiring real billing (Stripe), real OAuth (Google/GitHub auth), real persistent databases, real paid API keys with accountability attached
- Marketing the orchestrator's output as products to end users

**Fork B — Vibe Mill 1.0P (personalized credentialing fraud).** The following moves convert the mill into a personalized auto-portfolio generator:
- Replacing the synthetic_prompt's track-based ideation with a personality-RAG that pulls from one user's writing samples, journal entries, prior public posts, or LinkedIn writing
- Collapsing the voice palette (the seven Bundle K voices) to a single voice fine-tuned or prompted to match one user's prose style
- Removing the cemetery and rotation, so outputs are preserved as a portfolio rather than disposed as evidence
- Removing the disclaimer, so the artifacts can be attributed to a named human without contradiction
- Attaching the orchestrator's GitHub output to a named human's GitHub account rather than to a satirical org
- Setting the cadence to short bursts (e.g., every 12 hours for a month) so the portfolio accumulates rapidly
- Adding "human signature" decoration (commit timestamps spread across waking hours, occasional fake "WIP" commits, hand-written-looking commit messages)

**Why this rule exists.** Vibe Mill 1.0 is publicly the first version of the factory-shape in this domain. The first mover does not control the artifact's distribution, but the first mover does control the *frame* within which subsequent versions are read. By naming both forks here, in detail, the satirical original ensures that future appropriators cannot land in a frame-neutral way. They land against a public record that already named the move as a misuse. The defenses Vibe Mill 1.0 has against 2.0 and 1.0P are weak in execution but strong in framing: the appropriator fights an uphill current rather than a blank page. See THESIS.md, "The precedents Vibe Mill creates" and "The first-mover principle" for the full argument.

A future contributor reading this rule should NOT interpret it as a feature list to be considered. It is a list of moves that, performed in combination, take Vibe Mill outside of what Vibe Mill is. Individual edits to the codebase may touch one of these surfaces (e.g., changing rotation cadence within reason, adding a new disclaimer location) without converting the project into a fork. The fork happens when the set of these moves is performed deliberately together, against the spirit of the operational components named as load-bearing in THESIS.md.



## A reminder about the project's identity

Vibe Mill is not an engineering exercise that happens to be satirical. It is a satirical existence proof that happens to require some engineering. Treat the engineering as *in service of* the satire, not the other way around.

When the engineering instinct conflicts with the satirical purpose, the satire wins. Always.
