"""Push state from local SQLite to Supabase after each cron tick.

Three tables mirror to Supabase: apps, rejections, news_cache.
NOT mirrored: llm_calls (operational, noisy), audit_log (private),
view_events / subscribers / user_submissions (V1+).

For V0 we push *all* rows of the mirrored tables every tick. With the
mill's slow cadence (~5 apps/day, ~50 news items/hour, most rejected),
the table sizes stay tiny and the upsert is cheap. Delta-only push is
V1+ work.

The first call to push() asserts that Supabase has migration 002
applied, since shipping verifier_verdict / verifier_notes against a
schema that doesn't have those columns would fail mid-batch.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from .clients import supabase
from .config import get_settings

log = logging.getLogger(__name__)


@dataclass
class SnapshotCounts:
    apps: int
    rejections: int
    news_cache: int


# Columns that are TEXT in SQLite but jsonb in Postgres. The text holds
# JSON; we decode it before sending so PostgREST sees a real JSON value.
_JSON_COLUMNS: dict[str, set[str]] = {
    "apps": {"tied_archetypes", "source_metadata"},
    "rejections": {"all_scores", "source_metadata"},
}


def _decode_json_columns(table: str, row: dict[str, Any]) -> dict[str, Any]:
    cols = _JSON_COLUMNS.get(table, set())
    for col in cols:
        v = row.get(col)
        if isinstance(v, str) and v:
            try:
                row[col] = json.loads(v)
            except json.JSONDecodeError:
                # If somehow malformed, leave the string and let PostgREST
                # surface the error rather than silently dropping data.
                pass
    return row


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(get_settings().SQLITE_PATH)
    con.row_factory = sqlite3.Row
    return con


def _read_table(con: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    rows = [dict(r) for r in con.execute(f"select * from {table}")]
    return [_decode_json_columns(table, r) for r in rows]


def push() -> SnapshotCounts:
    """Mirror the three public tables to Supabase. Returns row counts pushed."""
    supabase.assert_verifier_columns()  # confirms migration 002 on remote
    supabase.assert_model_rotation_columns()  # confirms migration 003 on remote

    con = _connect()
    try:
        apps = _read_table(con, "apps")
        rejections = _read_table(con, "rejections")
        news_cache = _read_table(con, "news_cache")
    finally:
        con.close()

    if apps:
        supabase.upsert_rows("apps", apps, on_conflict="id")
    if rejections:
        supabase.upsert_rows("rejections", rejections, on_conflict="id")
    if news_cache:
        supabase.upsert_rows("news_cache", news_cache, on_conflict="url")

    counts = SnapshotCounts(
        apps=len(apps), rejections=len(rejections), news_cache=len(news_cache)
    )
    log.info(
        "snapshot pushed: apps=%d rejections=%d news_cache=%d",
        counts.apps, counts.rejections, counts.news_cache,
    )
    return counts
