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

For inputs that pass the guard, the matcher scores against all 12 archetypes and selects one or rejects.

### Prompt: `prompts/matcher.txt`

```
You are the matcher for Vibe Mill, an automated satirical app generator.
You score input prompts against twelve possible app archetypes and pick
the best fit, or reject if none fit well.

The twelve archetypes are:

1. Tracker — quantifiable ongoing event with geography or timeline
2. Parody UI — named entity plus content dump in familiar interface
3. Case-file browser — qualitative documents on rolling release
4. Counter game — absurd viral phrase or repeated action
5. Disruption visualizer — choke point with downstream ripples
6. Diaspora map — scattered group whose tracing is the story
7. Legal-action tracker — multi-front legal or political campaign
8. Mutual aid coordinator — service gap with community response
9. Wordle redux — finite entity space guessable by attributes
10. Glorified to-do — small life-utility checklist
11. Glorified social — niche community needing a feed
12. Recommendation engine — preferences in, single recommendation out

For the given input, score each archetype 0-10 based on how well the input
fits that archetype's spirit and example domains.

Scoring guide:
- 0-3: archetype is wrong for this input
- 4-6: input could stretch into this archetype but it would be a poor fit
- 7-8: input is a reasonable fit for this archetype
- 9-10: input is a near-prototypical example of this archetype

Threshold for selection is 7. If no archetype scores 7 or higher, reject
with reason "no archetype match."

If multiple archetypes tie at the highest score and that score is 7 or
higher, list all tied archetypes; the orchestrator will randomly select
among them.

Respond in JSON only:

{
  "scores": {
    "tracker": 0,
    "parody_ui": 0,
    "case_file_browser": 0,
    "counter_game": 0,
    "disruption_visualizer": 0,
    "diaspora_map": 0,
    "legal_action_tracker": 0,
    "mutual_aid_coordinator": 0,
    "wordle_redux": 0,
    "glorified_todo": 0,
    "glorified_social": 0,
    "recommendation_engine": 0
  },
  "selected_archetypes": ["tracker"],  // list of all archetypes at the highest score, if >= 7
  "reasoning": "one to two sentence rationale for the top score"
}

Input prompt:
{INPUT}
```

### Tie-breaking

If `selected_archetypes` contains more than one archetype, the orchestrator picks one uniformly at random. The full `scores` object is stored in `rejections.all_scores` (even when the input passes) for transparency and for the rejection sidebar to display occasional "the dice rolled" entries.

### V0 special case

In V0, only Tracker is implemented. The matcher prompt should still score all 12 (this gives us calibration data for V1) but the orchestrator filters: if the selected archetype is anything other than Tracker, treat as rejection with reason `archetype not yet implemented`.

This is a temporary V0 behavior, removed in V1.

## Calibration

Before the orchestrator runs in production, run the matcher offline against a fixed set of test inputs and verify the scores look reasonable. Suggested calibration set:

- "Hantavirus outbreak on cruise ship MV Hondius" → Tracker (high), Diaspora map (high), others low
- "Pope Leo and Trump tension" → all low (cultural, not data-shaped)
- "Strait of Hormuz tanker traffic disruption" → Disruption visualizer (high), Tracker (medium)
- "67 viral phrase keeps appearing in classrooms" → Counter game (high)
- "Epstein emails released by DOJ" → Parody UI (high), Case-file browser (high)
- "Trans rights legal cases proliferating across states" → Legal-action tracker (high)
- "FEMA disaster response capacity changes" → Mutual aid coordinator (high), Tracker (medium)
- "App for tracking my coffee intake" → Glorified to-do (high), Tracker (medium)
- "Twitter for declassified UFO researchers" → Glorified social (high)

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
