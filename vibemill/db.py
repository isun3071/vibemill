"""SQLite source of truth.

Migrations under `migrations/sqlite/` are the authoritative schema. The
sqlmodel classes here mirror those tables for typed queries. We do *not*
call `SQLModel.metadata.create_all()` — that would diverge from the
migration files. `apply_migrations()` runs the .sql files in lexical order
and tracks which have run in a `schema_migrations` table.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select, text

from .config import get_settings
from .models import (
    AppRecord,
    AppStatus,
    DeathCause,
    LlmCall,
    LlmPurpose,
    MatcherScores,
    RejectionRecord,
    RejectionStage,
    ScreenshotStatus,
    SourceKind,
)

log = logging.getLogger(__name__)


# =========================================================================
# sqlmodel classes (table=True) mirroring migrations/sqlite/001_init.sql
# =========================================================================


class App(SQLModel, table=True):
    __tablename__ = "apps"
    id: str = Field(primary_key=True)
    prompt: str
    archetype: str
    archetype_score: int
    tied_archetypes: str | None = None  # JSON-encoded list[str]
    github_url: str | None = None
    vercel_url: str | None = None
    screenshot_path: str | None = None
    screenshot_status: str = "pending"
    generation_cost_usd: float | None = None
    generation_seconds: int | None = None
    retry_count: int = 0
    source: str = "news"
    source_metadata: str | None = None  # JSON
    status: str = "live"
    death_cause: str | None = None
    views_total: int = 0
    views_peak_concurrent: int = 0
    declared_viral_at: str | None = None
    viral_extension_until: str | None = None
    created_at: str | None = None
    retired_at: str | None = None


class Rejection(SQLModel, table=True):
    __tablename__ = "rejections"
    id: str = Field(primary_key=True)
    source: str
    prompt: str
    rejection_stage: str
    rejection_reason: str | None = None
    best_archetype: str | None = None
    best_score: int | None = None
    all_scores: str | None = None  # JSON
    source_metadata: str | None = None  # JSON
    created_at: str | None = None


class NewsCacheRow(SQLModel, table=True):
    __tablename__ = "news_cache"
    url: str = Field(primary_key=True)
    headline: str
    feed_source: str
    published_at: str | None = None
    fetched_at: str | None = None
    guard_status: str | None = None
    matched_archetype: str | None = None
    matcher_score: int | None = None
    resulted_in_app: str | None = None


class LlmCallRow(SQLModel, table=True):
    __tablename__ = "llm_calls"
    id: int | None = Field(default=None, primary_key=True)
    called_at: str | None = None
    model: str
    purpose: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int | None = None
    app_id: str | None = None
    ok: int = 1


class AuditLogRow(SQLModel, table=True):
    __tablename__ = "audit_log"
    id: int | None = Field(default=None, primary_key=True)
    ts: str | None = None
    operator: str
    operation: str
    target: str | None = None
    reason: str | None = None


# =========================================================================
# Engine + migration runner
# =========================================================================

_engine: Engine | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        path = settings.SQLITE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{path}", echo=False)
        apply_migrations(_engine, settings.migrations_sqlite_dir)
    return _engine


@contextmanager
def session() -> Iterator[Session]:
    with Session(get_engine()) as s:
        yield s


def apply_migrations(engine: Engine, migrations_dir: Path) -> list[str]:
    """Apply any unapplied .sql files in `migrations_dir` in lexical order.

    Tracks applied filenames in a `schema_migrations` table. Returns the
    list of newly-applied filenames.
    """
    raw = sqlite3.connect(engine.url.database)  # type: ignore[arg-type]
    try:
        raw.execute(
            "create table if not exists schema_migrations ("
            "filename text primary key, "
            "applied_at text not null default current_timestamp)"
        )
        applied = {row[0] for row in raw.execute("select filename from schema_migrations")}
        new: list[str] = []
        for path in sorted(migrations_dir.glob("*.sql")):
            if path.name in applied:
                continue
            log.info("applying migration %s", path.name)
            raw.executescript(path.read_text())
            raw.execute("insert into schema_migrations (filename) values (?)", (path.name,))
            raw.commit()
            new.append(path.name)
        return new
    finally:
        raw.close()


# =========================================================================
# Apps
# =========================================================================


def insert_app(record: AppRecord) -> None:
    row = App(
        id=record.id,
        prompt=record.prompt,
        archetype=record.archetype,
        archetype_score=record.archetype_score,
        tied_archetypes=json.dumps(record.tied_archetypes) if record.tied_archetypes else None,
        github_url=record.github_url,
        vercel_url=record.vercel_url,
        screenshot_path=record.screenshot_path,
        screenshot_status=record.screenshot_status,
        generation_cost_usd=record.generation_cost_usd,
        generation_seconds=record.generation_seconds,
        retry_count=record.retry_count,
        source=record.source,
        source_metadata=json.dumps(record.source_metadata) if record.source_metadata else None,
        status=record.status,
        death_cause=record.death_cause,
        views_total=record.views_total,
        views_peak_concurrent=record.views_peak_concurrent,
        declared_viral_at=(
            record.declared_viral_at.strftime("%Y-%m-%dT%H:%M:%SZ")
            if record.declared_viral_at else None
        ),
        viral_extension_until=(
            record.viral_extension_until.strftime("%Y-%m-%dT%H:%M:%SZ")
            if record.viral_extension_until else None
        ),
        created_at=record.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        if record.created_at else _utc_now_iso(),
        retired_at=(
            record.retired_at.strftime("%Y-%m-%dT%H:%M:%SZ") if record.retired_at else None
        ),
    )
    with session() as s:
        s.add(row)
        s.commit()


def update_app(
    app_id: str,
    *,
    status: AppStatus | None = None,
    death_cause: DeathCause | None = None,
    retired_at: datetime | None = None,
    screenshot_path: str | None = None,
    screenshot_status: ScreenshotStatus | None = None,
    github_url: str | None = None,
    vercel_url: str | None = None,
) -> None:
    with session() as s:
        row = s.get(App, app_id)
        if row is None:
            raise KeyError(app_id)
        if status is not None:
            row.status = status
        if death_cause is not None:
            row.death_cause = death_cause
        if retired_at is not None:
            row.retired_at = retired_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        if screenshot_path is not None:
            row.screenshot_path = screenshot_path
        if screenshot_status is not None:
            row.screenshot_status = screenshot_status
        if github_url is not None:
            row.github_url = github_url
        if vercel_url is not None:
            row.vercel_url = vercel_url
        s.add(row)
        s.commit()


def get_app(app_id: str) -> App | None:
    with session() as s:
        return s.get(App, app_id)


def list_live_apps_oldest_first() -> list[App]:
    """Return live, non-viral apps ordered by created_at ascending."""
    with session() as s:
        stmt = select(App).where(App.status == "live").order_by(App.created_at.asc())  # type: ignore[union-attr]
        return list(s.exec(stmt))


def count_live_apps() -> int:
    with session() as s:
        result = s.exec(text("select count(*) from apps where status = 'live'"))
        return int(result.first()[0])  # type: ignore[index]


# =========================================================================
# Rejections
# =========================================================================


def insert_rejection(
    *,
    source: SourceKind,
    prompt: str,
    rejection_stage: RejectionStage,
    rejection_reason: str | None = None,
    best_archetype: str | None = None,
    best_score: int | None = None,
    all_scores: dict[str, int] | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> str:
    rid = str(uuid.uuid4())
    row = Rejection(
        id=rid,
        source=source,
        prompt=prompt,
        rejection_stage=rejection_stage,
        rejection_reason=rejection_reason,
        best_archetype=best_archetype,
        best_score=best_score,
        all_scores=json.dumps(all_scores) if all_scores else None,
        source_metadata=json.dumps(source_metadata) if source_metadata else None,
        created_at=_utc_now_iso(),
    )
    with session() as s:
        s.add(row)
        s.commit()
    return rid


# =========================================================================
# News cache
# =========================================================================


def get_cached_news(url: str) -> NewsCacheRow | None:
    with session() as s:
        return s.get(NewsCacheRow, url)


def upsert_news_cache(
    *,
    url: str,
    headline: str,
    feed_source: str,
    published_at: datetime | None = None,
    guard_status: str | None = None,
    matched_archetype: str | None = None,
    matcher_score: int | None = None,
    resulted_in_app: str | None = None,
) -> None:
    with session() as s:
        existing = s.get(NewsCacheRow, url)
        if existing is None:
            existing = NewsCacheRow(
                url=url,
                headline=headline,
                feed_source=feed_source,
                published_at=published_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                if published_at else None,
                fetched_at=_utc_now_iso(),
            )
        if guard_status is not None:
            existing.guard_status = guard_status
        if matched_archetype is not None:
            existing.matched_archetype = matched_archetype
        if matcher_score is not None:
            existing.matcher_score = matcher_score
        if resulted_in_app is not None:
            existing.resulted_in_app = resulted_in_app
        s.add(existing)
        s.commit()


# =========================================================================
# LLM cost ledger
# =========================================================================


def record_llm_call(call: LlmCall) -> None:
    row = LlmCallRow(
        called_at=_utc_now_iso(),
        model=call.model,
        purpose=call.purpose,
        tokens_in=call.tokens_in,
        tokens_out=call.tokens_out,
        cost_usd=call.cost_usd,
        latency_ms=call.latency_ms,
        app_id=call.app_id,
        ok=1 if call.ok else 0,
    )
    with session() as s:
        s.add(row)
        s.commit()


def today_cost_usd() -> float:
    """Sum cost_usd for calls since 00:00 UTC today."""
    start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    with session() as s:
        result = s.exec(
            text("select coalesce(sum(cost_usd), 0) from llm_calls where called_at >= :start").bindparams(start=start)  # type: ignore[arg-type]
        )
        return float(result.first()[0])  # type: ignore[index]


# =========================================================================
# Audit log (used by audit.py; defined here to keep table mapping in one file)
# =========================================================================


def write_audit(operator: str, operation: str, target: str | None, reason: str | None) -> None:
    row = AuditLogRow(
        ts=_utc_now_iso(),
        operator=operator,
        operation=operation,
        target=target,
        reason=reason,
    )
    with session() as s:
        s.add(row)
        s.commit()
