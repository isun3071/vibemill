"""Rotation logic. Two entry points:

- run_rotation(): the daily-cron path. Counts live apps; if over the cap,
  retires the oldest non-viral apps until we're back at the cap.
- retire_app(app_id, reason): the manual path used by the CLI.

What 'retire' means (per OPERATIONS.md):
1. Mark status='archived', retired_at=now, death_cause set
2. Archive the GitHub repo (PATCH archived=true; preserves the artifact)
3. Delete the deploy target. Bundle H: per-archetype dispatch — Vercel
   project for JS apps, HF Space for Python apps. Both deploy targets
   are paid/quota-limited; deletion frees the slot. The GitHub repo is
   archived in step 2 regardless, since GitHub holds the canonical
   source for every app (both rails mirror to GitHub at create time).
4. Audit log the action
5. (Caller pushes the snapshot; rotation does not push per-app)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from . import audit, db, snapshot
from .clients import github, hf_spaces, vercel
from .config import get_settings

log = logging.getLogger(__name__)


@dataclass
class RetireOutcome:
    app_id: str
    github_archived: bool
    deploy_deleted: bool   # Vercel project OR HF Space, depending on deploy_target


def _now_iso() -> datetime:
    return datetime.now(timezone.utc)


def _delete_deploy(app_id: str, deploy_target: str | None) -> bool:
    """Delete the live deployment for this app. Returns True on success.

    Bundle H: dispatch on deploy_target. Legacy apps (deploy_target is None
    because they were shipped before migration 010) default to Vercel,
    matching pre-Bundle-H behavior.
    """
    target = deploy_target or "vercel"
    if target == "hf_spaces":
        hf_spaces.delete_space(app_id)
    else:
        vercel.delete_project(app_id)
    return True


def retire_app(app_id: str, *, reason: str = "manual") -> RetireOutcome:
    """Retire one app. Used by both the rotation cron and the CLI.

    Per OPERATIONS.md the GitHub archive and deploy-target delete each fail
    independently; we record what succeeded and proceed. The status
    transition in SQLite happens last so a retry after partial failure
    will still attempt the cleanup steps.
    """
    app = db.get_app(app_id)
    if app is None:
        raise KeyError(f"app {app_id!r} not found")

    death_cause = "rotation" if reason == "rotation" else "manual"
    log.info("retire %s (cause=%s deploy_target=%s)", app_id, death_cause, app.deploy_target)

    archived = False
    try:
        github.archive_repo(app_id)
        archived = True
    except Exception as exc:
        log.warning("retire %s: github archive failed: %s", app_id, exc)

    deleted = False
    try:
        deleted = _delete_deploy(app_id, app.deploy_target)
    except Exception as exc:
        log.warning(
            "retire %s: deploy delete (target=%s) failed: %s",
            app_id, app.deploy_target, exc,
        )

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
        reason=f"github_archived={archived} deploy_deleted={deleted} target={app.deploy_target} cause={death_cause}",
    )
    return RetireOutcome(app_id=app_id, github_archived=archived, deploy_deleted=deleted)


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
