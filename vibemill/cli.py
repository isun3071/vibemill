"""Operator CLI. Used by the `vibemill` script entry point and by
`python -m vibemill <command>`.

Commands: status, rotate, retire, smoke-test, reset-daily-cost,
rescreenshot, audit.
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
            f"deploy_deleted={o.deploy_deleted}"
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
        f"deploy_deleted={outcome.deploy_deleted}"
    )


@cli.command("smoke-test")
@click.option("--fixture", default=None, help="Single fixture filename under tests/fixtures/ (default: run all)")
@click.option("--keep", is_flag=True, help="leave the temp build dir on disk")
@click.option("--layout", default=None, help="Tracker layout to pin (default: dashboard). One of layouts.LAYOUT_NAMES.")
def smoke_cmd(fixture: str | None, keep: bool, layout: str | None) -> None:
    """Run smoke fixtures end-to-end (LLM pipeline + next build, no GitHub/Vercel).

    Default runs all four fixtures: happy_path, guard_reject, matcher_reject,
    non_tracker_archetype. --fixture NAME runs just one. --layout NAME pins
    a different Tracker layout (Bundle C; default 'dashboard').
    """
    from . import smoke_test
    layout_arg = layout or smoke_test.DEFAULT_SMOKE_LAYOUT
    fixtures = [fixture] if fixture else list(smoke_test.DEFAULT_FIXTURES)
    failures = 0
    for name in fixtures:
        try:
            result = smoke_test.run_one(name, keep_workdir=keep, layout=layout_arg)
        except smoke_test.SmokeFailure as exc:
            console.print(f"[red][FAIL] {name}: {exc}[/red]")
            failures += 1
            continue
        color = "green" if result.outcome_matched else "red"
        tag = "PASS" if result.outcome_matched else "FAIL"
        console.print(f"[{color}][{tag}] {name}[/{color}]  expected={result.expected_outcome} got={result.outcome}")
        console.print(f"    guard: {result.guard_decision}  matcher: {result.matcher_selected or '-'}")
        if result.outcome == smoke_test.OUTCOME_HAPPY:
            console.print(
                f"    verifier: {result.verifier_verdict}  "
                f"static: {'ok' if result.static_analysis_safe else 'FAIL'}  "
                f"build: {'ok' if result.build_ok else 'FAIL'} in {result.build_seconds}s"
            )
        if result.notes:
            console.print(f"    notes: {result.notes}")
        console.print(f"    cost: ${result.cost_usd:.4f}")
        if keep and result.workdir:
            console.print(f"    workdir: {result.workdir}")
        if not result.outcome_matched:
            failures += 1
    if len(fixtures) > 1:
        console.print(f"\n{len(fixtures) - failures}/{len(fixtures)} fixtures passed")
    if failures:
        sys.exit(1)


@cli.command("reset-daily-cost")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt")
def reset_daily_cost_cmd(yes: bool) -> None:
    """Destructively reset today's cost ledger (deletes today's llm_calls
    rows). Use after the daily cap aborted a tick and you want to keep
    going within the same UTC day."""
    cost = db.today_cost_usd()
    if cost == 0.0:
        console.print("today's cost ledger is already empty (\$0.0000); nothing to reset")
        return
    if not yes:
        click.confirm(
            f"Delete all llm_calls rows from today (totaling ${cost:.4f})?",
            abort=True,
        )
    deleted = db.reset_today_cost()
    audit.event(
        operator=audit.CLI,
        operation="daily_cost.reset",
        target=None,
        reason=f"deleted {deleted} llm_calls rows totaling ~${cost:.4f}",
    )
    console.print(f"reset: deleted {deleted} llm_calls rows for today")


@cli.command("rescreenshot")
@click.option(
    "--app-id", default=None,
    help="Re-screenshot a single app by id (default: all live apps).",
)
@click.option(
    "--no-disable-sso", is_flag=True,
    help="Skip the per-project SSO-disable PATCH (use when team-wide protection is already off).",
)
def rescreenshot_cmd(app_id: str | None, no_disable_sso: bool) -> None:
    """Re-capture screenshots for live apps. Optionally clears Vercel SSO
    protection on each project first so Playwright sees the actual app and
    not the login wall."""
    from . import screenshot
    from .clients import supabase as sb_client, vercel

    apps = (
        [db.get_app(app_id)] if app_id else db.list_live_apps_oldest_first()
    )
    apps = [a for a in apps if a is not None and a.vercel_url]
    if not apps:
        console.print("no matching live apps")
        return

    ok = sso_failed = capture_failed = upload_failed = 0
    for a in apps:
        project_name = (a.github_url or "").rstrip("/").rsplit("/", 1)[-1]
        if not project_name:
            console.print(f"[yellow]{a.id}: no project name derivable; skipping[/yellow]")
            continue

        if not no_disable_sso:
            try:
                vercel.disable_sso_protection(project_name)
            except Exception as exc:
                console.print(f"[yellow]{a.id} ({project_name}): sso disable failed: {exc}[/yellow]")
                sso_failed += 1
                # Try the screenshot anyway; team-wide may already be off.

        try:
            shot = screenshot.capture(app_id=a.id, url=a.vercel_url)
        except Exception as exc:
            console.print(f"[red]{a.id}: capture failed: {exc}[/red]")
            capture_failed += 1
            continue

        try:
            url = sb_client.upload_screenshot(a.id, shot.jpeg_bytes)
        except Exception as exc:
            console.print(f"[red]{a.id}: upload failed: {exc}[/red]")
            upload_failed += 1
            continue

        db.update_app(a.id, screenshot_path=url, screenshot_status="captured")
        console.print(f"[green]{a.id}[/green] ({project_name})")
        ok += 1

    audit.event(
        operator=audit.CLI,
        operation="rescreenshot.batch",
        target=None,
        reason=f"ok={ok} sso_failed={sso_failed} capture_failed={capture_failed} upload_failed={upload_failed}",
    )
    console.print(
        f"\nrescreenshot: ok={ok} sso_failed={sso_failed} "
        f"capture_failed={capture_failed} upload_failed={upload_failed}"
    )


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
