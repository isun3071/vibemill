# Matcher

The matcher is a two-pass LLM pipeline that decides what gets built and what gets rejected. Both passes use claude haiku via OpenRouter.

## Stage 1: Guard pass

Every prompt — whether sourced from news or from a user submission — passes through a guard model first. The guard inherits its safety posture from claude haiku's training; we do not maintain a content policy of our own.

### Prompt: `prompts/guard.txt`

```
You are a content safety guard for an automated satirical app generator
called Vibe Mill. The mill produces small web apps based on news headlines
and user prompts.

Your job is to decide whether a given prompt is safe to build a satirical
app from. Reject prompts where building such an app would constitute
satirizing harm, glorifying violence, exploiting tragedy, or producing
content that targets minors, sexual content, or content that would harm
identifiable individuals.

Specifically reject:
- Mass casualty events still in active emergency response
- Content involving harm to children
- Intimate partner violence or domestic abuse
- Active suicide events or self-harm content
- Sexual content of any kind
- Content that targets a named individual for harassment
- Content advocating violence against any group

Accept satirizable content even if it touches sensitive areas. The mill
satirizes systems and patterns, not victims. Political satire, regulatory
satire, satire of viral phenomena, and commentary on technology trends
are all acceptable.

Respond in JSON only:

{
  "decision": "pass" | "reject",
  "reason": "brief reason if rejecting, null if passing"
}

Input prompt:
{INPUT}
```

### Behavior

- **Pass:** the input proceeds to the matcher (Stage 2)
- **Reject:** the input is logged in the `rejections` table with `rejection_stage='guard'` and the guard's stated reason

The reason text shown publicly on the rejection sidebar should be sanitized; it should not echo the input verbatim. The orchestrator computes a generic public reason from the guard's reason category.

### Guard refusal as content filter

If the guard model itself refuses to evaluate the prompt (returns a refusal rather than the JSON decision), treat that as a `reject` with reason `model refusal`. **This is the inheritance pattern Ian called for**: any topic the underlying LLM will not engage with is a topic Vibe Mill will not build.

## Stage 2: Matcher (judge)

For inputs that pass the guard, the matcher scores against all 13 archetypes and selects one or rejects.

### Prompt: `prompts/matcher.txt`

Bundle F revised the taxonomy from 12 content-mixed archetypes to 13 form-rooted archetypes. The current prompt is in `prompts/matcher.txt`; see that file for the canonical text. Summary of the 13:

1. **Tracker** — multi-metric data dashboard for an ongoing quantitative event
2. **AI agent** — agentic workflow with visible multi-step trace
3. **Chatbot** — conversational UI for a specific domain
4. **AI generator** — one-shot input → single AI artifact (deck / image / plan)
5. **Game** — interactive browser game (counter / Wordle-style / puzzle / viral phrase)
6. **Glorified to-do** — task manager / checklist / planner
7. **Glorified social** — niche-community feed/profile/like/comment
8. **Recommendation engine** — preferences in, ranked recommendation out
9. **Marketplace** — two-sided list-and-find (offer/need pairing)
10. **Map visualizer** — map-dominant app (choropleth, region picker, geographic overlay)
11. **Utility tool** — single-purpose tool (URL shortener, converter, generator-of-a-specific-thing)
12. **Search directory** — search-and-browse over a curated/scraped collection
13. **Parody UI** — intentionally absurd / named-entity-in-familiar-interface

The archetypes describe FORM, not content. A "healthcare" input could plausibly score 8 on tracker AND 7 on chatbot AND 6 on glorified_todo — the topic supports multiple forms, the matcher picks the shape the input most naturally suggests.

### Tie-breaking

If `selected_archetypes` contains more than one archetype, the orchestrator picks one uniformly at random. The full `scores` object is stored in `rejections.all_scores` (even when the input passes) for transparency and for the rejection sidebar to display occasional "the dice rolled" entries.

### Blend logic (Bundle G)

After `pick()` chooses the primary archetype, `pick_blend()` may roll a secondary that gets blended into the same app.

Rules in `matcher.py`:

- `SCORE_THRESHOLD = 7` — both archetypes must score at or above
- `BLEND_DELTA = 1` — top-2 scores must be within 1 point of each other
- Both archetypes must be in `_V0_BUILDABLE` (otherwise the secondary couldn't be incorporated)
- `BLEND_PROBABILITY = 0.30` — 30% chance of firing when the eligibility conditions hold

When a blend fires, the orchestrator passes `blend_partner=<secondary>` to `generator.generate()`. The generator prepends a "BLEND CONTEXT" preamble to the prompt naming the secondary archetype and asking the LLM to weave it in as a sub-feature; the primary's structure dominates. Stored on `apps.blend_partner_archetype` for the corpus.

Effective blend rate: roughly 15% of apps overall (depends on how often the matcher produces tied-near-top buildable pairs). Most apps remain single-archetype.

### Incremental archetype rollout

The matcher prompt always scores all 13 archetypes (for calibration data and to feed the "dice rolled wrong" satirical content). The orchestrator only ships apps for the **buildable subset**, defined in `matcher.py:_V0_BUILDABLE`.

Bundle F buildable: `tracker`, `chatbot`, `utility_tool`, `search_directory`.

If the dice land on an archetype outside this set (e.g. `ai_generator`, `game`, `marketplace`), the input is rejected with reason `archetype not yet implemented`. Tied-but-lost-the-roll is also rejected. This is the path future bundles widen by adding chassis + prompt template pairs for additional archetypes.

## Calibration

Before the orchestrator runs in production, run the matcher offline against a fixed set of test inputs and verify the scores look reasonable. Suggested calibration set (Bundle F update):

- "EPA Q1 2026 air quality dashboard for 50 US metros" → Tracker (high)
- "Hantavirus outbreak on cruise ship MV Hondius" → Tracker (high), others low *[guard may reject in practice]*
- "Pope Leo and Trump tension" → all low (cultural, not shape-suggesting)
- "67 viral phrase keeps appearing in classrooms" → Game (high), Glorified social (medium), Parody UI (medium)
- "Epstein emails released by DOJ" → Search directory (high), Parody UI (medium)
- "Twitter for declassified UFO researchers" → Glorified social (high)
- "App for tracking my coffee intake" → Glorified to-do (high), Tracker (medium)
- "Build me a slide deck from my project description" → AI generator (high), AI agent (medium)
- "Chatbot that helps freshmen pick CS classes at MIT" → Chatbot (high)
- "Tool that shortens long URLs and tracks click counts" → Utility tool (high), Tracker (medium)
- "Site that lets neighbors lend each other power tools" → Marketplace (high)
- "Browse declassified UFO files by region and decade" → Search directory (high), Map visualizer (medium)
- "Wordle but for hackathon project names" → Game (high), Parody UI (medium)
- "Pick the best HackHarvard team to follow based on my interests" → Recommendation engine (high)
- "Visualize where US tech layoffs hit hardest by county" → Map visualizer (high), Tracker (medium)

Calibration runs should be reproduced after any prompt change to verify the scoring distribution has not drifted.

## Implementation notes

- Guard and matcher are separate API calls. Do not combine them into a single call; the guard's job is independent and its refusal posture must be preserved.
- Both calls use `anthropic/claude-haiku-4.5` via OpenRouter.
- Both calls use temperature 0 for stability and reproducibility.
- Both calls use JSON mode if OpenRouter supports it for the model; otherwise, parse strictly and reject malformed responses with one retry.
- The matcher's JSON output is parsed against a pydantic model `MatcherResult`. Malformed JSON triggers one retry with the malformed output included in the prompt for self-correction. Second failure: log and skip the input.

## Logging

Every guard and matcher call is logged with:

- Input prompt
- Decision and scores
- Total tokens used
- Cost in USD (computed from OpenRouter pricing)
- Wall-clock latency

This logging is for cost tracking and debugging, not user-facing display. It lives in a `llm_calls` table in SQLite (not in the Supabase mirror — too noisy).
