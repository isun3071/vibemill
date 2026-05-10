"""Pydantic models for inter-module data transfer.

Two kinds of models live here:
- LLM I/O: GuardResult, MatcherScores, MatcherResult, GeneratorOutput
- Pipeline values: NewsItem, LlmCall, GeneratedSlots, AppRecord

DB row types live in `db.py` as sqlmodel classes; the pipeline models here
are deliberately decoupled from persistence so the same shape can flow
through smoke tests without touching SQLite.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# Archetype names match the JSON keys the matcher emits (snake_case).
ARCHETYPE_NAMES: tuple[str, ...] = (
    "tracker",
    "parody_ui",
    "case_file_browser",
    "counter_game",
    "disruption_visualizer",
    "diaspora_map",
    "legal_action_tracker",
    "mutual_aid_coordinator",
    "wordle_redux",
    "glorified_todo",
    "glorified_social",
    "recommendation_engine",
)

ArchetypeName = Literal[
    "tracker",
    "parody_ui",
    "case_file_browser",
    "counter_game",
    "disruption_visualizer",
    "diaspora_map",
    "legal_action_tracker",
    "mutual_aid_coordinator",
    "wordle_redux",
    "glorified_todo",
    "glorified_social",
    "recommendation_engine",
]

GuardDecision = Literal["pass", "reject"]
LlmPurpose = Literal["guard", "matcher", "generator", "readme", "name", "search"]
AppStatus = Literal["live", "archived", "stillborn", "viral"]
DeathCause = Literal["rotation", "manual", "never_built"]
RejectionStage = Literal["guard", "matcher"]
ScreenshotStatus = Literal["pending", "captured", "missing"]
SourceKind = Literal["news", "user_submitted"]


class NewsItem(BaseModel):
    """A single news story pulled from RSS."""

    url: str
    headline: str
    summary: str = ""
    feed_source: str  # 'ap' | 'bbc'
    published_at: datetime | None = None


class GuardResult(BaseModel):
    decision: GuardDecision
    reason: str | None = None


class MatcherScores(BaseModel):
    tracker: int = Field(0, ge=0, le=10)
    parody_ui: int = Field(0, ge=0, le=10)
    case_file_browser: int = Field(0, ge=0, le=10)
    counter_game: int = Field(0, ge=0, le=10)
    disruption_visualizer: int = Field(0, ge=0, le=10)
    diaspora_map: int = Field(0, ge=0, le=10)
    legal_action_tracker: int = Field(0, ge=0, le=10)
    mutual_aid_coordinator: int = Field(0, ge=0, le=10)
    wordle_redux: int = Field(0, ge=0, le=10)
    glorified_todo: int = Field(0, ge=0, le=10)
    glorified_social: int = Field(0, ge=0, le=10)
    recommendation_engine: int = Field(0, ge=0, le=10)

    def as_dict(self) -> dict[str, int]:
        return self.model_dump()

    def best(self) -> tuple[str, int]:
        items = self.as_dict().items()
        return max(items, key=lambda kv: kv[1])


class MatcherResult(BaseModel):
    scores: MatcherScores
    selected_archetypes: list[str] = Field(default_factory=list)
    reasoning: str = ""


class GeneratedFile(BaseModel):
    """One file in the generator's output. Path is chassis-relative
    (e.g. 'app/page.tsx', 'lib/components/Filter.tsx'). Path validation
    happens in generator.py before staging.

    Bundle D (multi-file generation): the LLM produces a variable-length
    list of these per app, sized per tier (slop ~2, mean_good 3-6,
    banger 4-8). Chassis-owned paths (layout.tsx, globals.css, configs)
    are silently dropped if the LLM tries to write them.
    """
    path: str
    content: str


class GeneratorOutput(BaseModel):
    """The set of slot files the generator LLM produces for an app.
    Variable length per tier per Bundle D. Validated for path safety +
    minimum-required-file (app/page.tsx) in generator.generate."""
    files: list[GeneratedFile]


class VerifierLLMResult(BaseModel):
    """Raw verifier LLM output. Verdict is free text but should be one of the
    three documented values per GENERATOR.md; we don't enforce with Literal so
    a slightly off verdict ("looks-good" vs "looks good") still parses.

    Bundle D: verifier returns the same file-list shape as the generator,
    possibly with edits. If the file list is missing/empty, fall through
    to the original generator output."""
    files: list[GeneratedFile] = Field(default_factory=list)
    verdict: str = ""
    notes: str = ""


class LlmCall(BaseModel):
    """One LLM invocation, recorded to the cost ledger."""

    model: str
    purpose: LlmPurpose
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int | None = None
    ok: bool = True
    app_id: str | None = None


class GeneratedSlots(BaseModel):
    """Generator + readme output combined; ready to write to a chassis tree."""

    page_tsx: str
    data_ts: str
    readme_md: str


class AppRecord(BaseModel):
    """An app the mill has produced. Matches the apps table."""

    id: str
    prompt: str
    archetype: str
    archetype_score: int
    tied_archetypes: list[str] | None = None
    github_url: str | None = None
    vercel_url: str | None = None
    screenshot_path: str | None = None
    screenshot_status: ScreenshotStatus = "pending"
    generation_cost_usd: float | None = None
    generation_seconds: int | None = None
    retry_count: int = 0
    source: SourceKind = "news"
    source_metadata: dict | None = None
    status: AppStatus = "live"
    death_cause: DeathCause | None = None
    views_total: int = 0
    views_peak_concurrent: int = 0
    declared_viral_at: datetime | None = None
    viral_extension_until: datetime | None = None
    created_at: datetime | None = None
    retired_at: datetime | None = None
    verifier_verdict: str | None = None
    verifier_notes: str | None = None
    generator_model: str | None = None
    readme_model: str | None = None
    committed_path: bool = False
    readme_persona: str | None = None
    # Migration 006: three-tier output calibration.
    tier: str | None = None  # 'slop' | 'mean_good' | 'banger'
    web_searched: bool = False
    search_queries_count: int = 0
    search_total_cost: float = 0.0
    # Migration 007: multi-file generation.
    file_count: int | None = None
    # Migration 008: Bundle C layout-archetype rotation within Tracker.
    layout_archetype: str | None = None


class RejectionRecord(BaseModel):
    id: str
    source: SourceKind
    prompt: str
    rejection_stage: RejectionStage
    rejection_reason: str | None = None
    best_archetype: str | None = None
    best_score: int | None = None
    all_scores: dict[str, int] | None = None
    source_metadata: dict | None = None
    created_at: datetime | None = None
