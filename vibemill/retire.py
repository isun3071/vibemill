"""Rotation logic. Two entry points:

- run_rotation(): the daily-cron path. Counts live apps; if over the cap,
  retires the oldest non-viral apps until we're back at the cap.
- retire_app(app_id, reason): the manual path used by the CLI.

What 'retire' means (per OPERATIONS.md):
1. Mark status='archived', retired_at=now, death_cause set
2. Archive the GitHub repo (PATCH archived=true; preserves the artifact)
3. Delete the Vercel project (Vercel has no archive concept; deletion frees
   the free-tier project slot)
4. Audit log the action
5. (Caller pushes the snapshot; rotation does not push per-app)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from . import audit, db, snapshot
from .clients import github, vercel
from .config import get_settings

log = logging.getLogger(__name__)


@dataclass
class RetireOutcome:
    app_id: str
    github_archived: bool
    vercel_deleted: bool


def _now_iso() -> datetime:
    return datetime.now(timezone.utc)


def retire_app(app_id: str, *, reason: str = "manual") -> RetireOutcome:
    """Retire one app. Used by both the rotation cron and the CLI.

    Per OPERATIONS.md the GitHub archive and Vercel delete each fail
    independently; we record what succeeded and proceed. The status
    transition in SQLite happens last so a retry after partial failure
    will still attempt the cleanup steps.
    """
    app = db.get_app(app_id)
    if app is None:
        raise KeyError(f"app {app_id!r} not found")

    death_cause = "rotation" if reason == "rotation" else "manual"
    log.info("retire %s (cause=%s)", app_id, death_cause)

    archived = False
    try:
        github.archive_repo(app_id)
        archived = True
    except Exception as exc:
        log.warning("retire %s: github archive failed: %s", app_id, exc)

    deleted = False
    try:
        vercel.delete_project(app_id)
        deleted = True
    except Exception as exc:
        log.warning("retire %s: vercel delete failed: %s", app_id, exc)

    db.update_app(
        app_id,
        status="archived",
        death_cause=death_cause,
        retired_at=_now_iso(),
    )
    audit.event(
        operator=audit.ORCHESTRATOR if reason == "rotation" else audit.CLI,
        operation="app.retire",
        target=app_id,
        reason=f"github_archived={archived} vercel_deleted={deleted} cause={death_cause}",
    )
    return RetireOutcome(app_id=app_id, github_archived=archived, vercel_deleted=deleted)


def run_rotation(*, push_snapshot: bool = True) -> list[RetireOutcome]:
    """Daily-cron entry. Retires the oldest non-viral live apps until we
    are back at LIVE_APP_CAP. Pushes a snapshot at the end unless caller
    suppresses (used by the CLI to batch its own snapshot push).
    """
    cap = get_settings().LIVE_APP_CAP
    live = db.list_live_apps_oldest_first()
    excess = len(live) - cap
    if excess <= 0:
        log.info("rotation: %d live apps, cap=%d, nothing to retire", len(live), cap)
        return []

    log.info("rotation: %d live apps, cap=%d, retiring %d oldest", len(live), cap, excess)
    outcomes: list[RetireOutcome] = []
    for app_row in live[:excess]:
        try:
            outcomes.append(retire_app(app_row.id, reason="rotation"))
        except Exception as exc:
            log.error("rotation: failed to retire %s: %s", app_row.id, exc)

    if push_snapshot:
        try:
            snapshot.push()
        except Exception as exc:
            log.warning("rotation: snapshot push failed (will retry next tick): %s", exc)

    return outcomes
