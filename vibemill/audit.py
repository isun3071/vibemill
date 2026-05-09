"""Audit log helper.

Every state-changing operation (app create, retire, viral extend, manual
intervention) writes a row to `audit_log`. This is for the operator's
reconstruction of "what happened on day X" and is never pushed to Supabase.
"""

from __future__ import annotations

import logging

from . import db

log = logging.getLogger(__name__)

ORCHESTRATOR = "orchestrator"
CLI = "cli"


def event(operator: str, operation: str, target: str | None = None, reason: str | None = None) -> None:
    """Record an audit event.

    Failures are logged but not raised: the audit trail must never block the
    operation it is recording.
    """
    try:
        db.write_audit(operator=operator, operation=operation, target=target, reason=reason)
    except Exception as exc:
        log.warning("audit write failed for %s/%s: %s", operator, operation, exc)
