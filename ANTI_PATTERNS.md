# Anti-Patterns

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
