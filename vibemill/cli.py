"""Operator CLI. Used by the `vibemill` script entry point and by
`python -m vibemill <command>`.

Commands: status, rotate, retire, smoke-test.
"""

from __future__ import annotations

import logging
import sys

import click
from rich.console import Console
from rich.table import Table

from . import audit, db, retire as retire_mod
from .config import get_settings


console = Console()
log = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """Vibe Mill operator commands."""


@cli.command("status")
def status_cmd() -> None:
    """Print live app count, today's cost, and recent activity."""
    settings = get_settings()
    live = db.count_live_apps()
    cost = db.today_cost_usd()
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("live apps", f"{live} / {settings.LIVE_APP_CAP}")
    table.add_row("today's LLM cost (USD)", f"${cost:.4f} / ${settings.DAILY_COST_CAP_USD:.2f}")
    table.add_row("sqlite path", str(settings.SQLITE_PATH))
    table.add_row("github org", settings.GITHUB_ORG)
    console.print(table)


@cli.command("rotate")
def rotate_cmd() -> None:
    """Retire oldest non-viral live apps until count == LIVE_APP_CAP."""
    outcomes = retire_mod.run_rotation()
    if not outcomes:
        console.print("nothing to retire")
        return
    for o in outcomes:
        console.print(
            f"retired {o.app_id}: github_archived={o.github_archived} "
            f"vercel_deleted={o.vercel_deleted}"
        )


@cli.command("retire")
@click.argument("app_id")
def retire_cmd(app_id: str) -> None:
    """Manually retire one app immediately."""
    try:
        outcome = retire_mod.retire_app(app_id, reason="manual")
    except KeyError:
        console.print(f"[red]no such app: {app_id}[/red]")
        sys.exit(1)
    console.print(
        f"retired {outcome.app_id}: github_archived={outcome.github_archived} "
        f"vercel_deleted={outcome.vercel_deleted}"
    )


@cli.command("smoke-test")
@click.option("--keep", is_flag=True, help="leave the temp build dir on disk")
def smoke_cmd(keep: bool) -> None:
    """Run the end-to-end smoke test (LLM pipeline + next build, no GitHub/Vercel)."""
    from . import smoke_test
    try:
        result = smoke_test.run(keep_workdir=keep)
    except Exception as exc:
        console.print(f"[red]smoke test FAILED: {exc}[/red]")
        sys.exit(1)
    console.print(f"[green]smoke test PASSED[/green]")
    console.print(f"  guard: {result.guard_decision}")
    console.print(f"  matcher selected: {result.matcher_selected}")
    console.print(f"  generator: {result.generator_chars} chars across two slots")
    console.print(f"  verifier verdict: {result.verifier_verdict}")
    console.print(f"  static analysis: {'OK' if result.static_analysis_safe else 'FAILED'}")
    console.print(f"  build: {'OK' if result.build_ok else 'FAILED'} in {result.build_seconds}s")
    if keep:
        console.print(f"  workdir: {result.workdir}")
    console.print(f"  total cost: ${result.cost_usd:.4f}")


@cli.command("audit")
@click.option("--limit", type=int, default=20)
def audit_cmd(limit: int) -> None:
    """Show recent audit_log entries (most recent first)."""
    from sqlmodel import select, desc
    from .db import AuditLogRow, session
    with session() as s:
        rows = list(s.exec(select(AuditLogRow).order_by(desc(AuditLogRow.id)).limit(limit)))
    table = Table(box=None)
    table.add_column("ts"); table.add_column("operator"); table.add_column("operation")
    table.add_column("target"); table.add_column("reason")
    for r in rows:
        table.add_row(r.ts or "-", r.operator, r.operation, r.target or "-", (r.reason or "")[:80])
    console.print(table)


if __name__ == "__main__":
    cli()
