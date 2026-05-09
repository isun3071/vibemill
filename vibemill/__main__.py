"""Cron-tick entry point.

Bare invocation:
    python -m vibemill
runs one cron tick: ingest news, guard + match, ship up to MAX_APPS_PER_TICK
new apps, snapshot to Supabase.

Subcommand invocation:
    python -m vibemill rotate
    python -m vibemill status
    python -m vibemill retire <app_id>
    python -m vibemill smoke-test
delegates to cli.cli().

Per OPERATIONS.md, per-app failures isolate: one stillborn does not abort
the cron tick. Per CLAUDE.md the daily cost cap is the kill switch: if
DAILY_COST_CAP_USD has already been exceeded at tick start, the tick aborts.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import (
    audit,
    db,
    generator,
    github_publish,
    guard,
    ingest,
    matcher,
    name_generator,
    readme_writer,
    retire,
    screenshot,
    security,
    snapshot,
    vercel_deploy,
    verify,
)
from .clients import supabase
from .config import get_settings
from .models import (
    AppRecord,
    GeneratorOutput,
    NewsItem,
)
from .verify import VERDICT_FAILED, VERDICT_LOOKS_GOOD

log = logging.getLogger(__name__)


# CLAUDE.md v3 changed the cadence from hourly to every 4 hours: 6 ticks/day
# instead of 24. To keep the 5-10 apps/day target, the per-tick budget rises
# from ~0.4 to ~1.7 apps. Cap at 5 to give one tick room to clear a backlog
# while still bounding worst-case cost spike.
MAX_APPS_PER_TICK = 5
NEXT_BUILD_TIMEOUT_S = 240


@dataclass
class TickResult:
    apps_shipped: int
    rejections: int
    stillborn: int
    skipped_cost_cap: bool


# ============================================================================
# Build harness
# ============================================================================


def _stage_chassis(
    src_chassis: Path,
    *,
    page_tsx: str,
    data_ts: str,
    readme_md: str,
) -> Path:
    """Copy the chassis into a tempdir, write the slot files, return the path."""
    work = Path(tempfile.mkdtemp(prefix="vibemill-build-"))
    shutil.copytree(src_chassis, work, dirs_exist_ok=True)
    (work / "app" / "page.tsx").write_text(page_tsx)
    (work / "lib" / "data.ts").write_text(data_ts)
    (work / "README.md").write_text(readme_md or "")
    return work


def _run_next_build(work: Path) -> tuple[bool, str]:
    """Run npm install + next build in the staged tree. Returns (ok, last_output)."""
    try:
        install = subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", "--silent"],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=NEXT_BUILD_TIMEOUT_S,
        )
        if install.returncode != 0:
            return False, f"npm install failed:\n{install.stderr[-1500:]}"

        build = subprocess.run(
            ["npx", "--yes", "next", "build"],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=NEXT_BUILD_TIMEOUT_S,
        )
        if build.returncode != 0:
            return False, f"next build failed:\n{build.stdout[-2000:]}\n---\n{build.stderr[-1000:]}"
        return True, build.stdout[-300:]
    except subprocess.TimeoutExpired as exc:
        return False, f"build timed out after {NEXT_BUILD_TIMEOUT_S}s: {exc}"
    except Exception as exc:
        return False, f"build harness error: {exc}"


# ============================================================================
# Per-app pipeline
# ============================================================================


def _ship_one(item: NewsItem) -> str:
    """Process one news item all the way to a live Vercel URL or a logged
    rejection / stillborn marker. Returns one of:
        'shipped' | 'rejected_guard' | 'rejected_matcher' | 'rejected_archetype'
        | 'stillborn_build' | 'stillborn_publish' | 'stillborn_deploy'
        | 'screenshot_missing'  (still shipped)
    """
    settings = get_settings()
    prompt = f"{item.headline}. {item.summary}".strip()

    # 1. Guard
    g = guard.check(prompt)
    if g.decision != "pass":
        db.insert_rejection(
            source="news",
            prompt=prompt,
            rejection_stage="guard",
            rejection_reason=g.reason,
            source_metadata={
                "url": item.url,
                "headline": item.headline,
                "feed": item.feed_source,
            },
        )
        db.upsert_news_cache(
            url=item.url,
            headline=item.headline,
            feed_source=item.feed_source,
            published_at=item.published_at,
            guard_status="rejected",
        )
        log.info("rejected at guard: %s | %s", item.headline[:60], g.reason)
        return "rejected_guard"

    # 2. Matcher
    m = matcher.score(prompt)
    if m is None:
        db.insert_rejection(
            source="news", prompt=prompt, rejection_stage="matcher",
            rejection_reason="matcher_error",
            source_metadata={"url": item.url, "headline": item.headline, "feed": item.feed_source},
        )
        db.upsert_news_cache(url=item.url, headline=item.headline, feed_source=item.feed_source,
                             published_at=item.published_at, guard_status="passed")
        return "rejected_matcher"

    picked = matcher.pick(m)
    best_archetype, best_score = m.scores.best()
    if picked is None:
        db.insert_rejection(
            source="news", prompt=prompt, rejection_stage="matcher",
            rejection_reason="no archetype match",
            best_archetype=best_archetype, best_score=best_score,
            all_scores=m.scores.as_dict(),
            source_metadata={"url": item.url, "headline": item.headline, "feed": item.feed_source},
        )
        db.upsert_news_cache(url=item.url, headline=item.headline, feed_source=item.feed_source,
                             published_at=item.published_at, guard_status="passed",
                             matched_archetype=best_archetype, matcher_score=best_score)
        log.info("rejected at matcher: %s | best=%s/%d", item.headline[:60], best_archetype, best_score)
        return "rejected_matcher"

    if not matcher.is_v0_buildable(picked):
        db.insert_rejection(
            source="news", prompt=prompt, rejection_stage="matcher",
            rejection_reason=f"archetype not yet implemented: {picked}",
            best_archetype=picked, best_score=m.scores.as_dict()[picked],
            all_scores=m.scores.as_dict(),
            source_metadata={"url": item.url, "headline": item.headline, "feed": item.feed_source},
        )
        db.upsert_news_cache(url=item.url, headline=item.headline, feed_source=item.feed_source,
                             published_at=item.published_at, guard_status="passed",
                             matched_archetype=picked)
        log.info("rejected (V0): %s rolled %s, only Tracker ships", item.headline[:60], picked)
        return "rejected_archetype"

    # We have a Tracker. Mint an id; persist it on the row at the end.
    app_id = name_generator.make_name()
    log.info("shipping %s (archetype=tracker, score=%d)", app_id, m.scores.tracker)
    started = datetime.now(timezone.utc)

    # 3. Generate -> verify -> static analysis -> build, with one retry on build
    # failure (per GENERATOR.md v3). Static analysis is a hard gate with NO
    # retry: a forbidden pattern is a policy violation, not a transient error.
    chassis_dir = settings.archetypes_dir / "tracker" / "chassis"
    work: Path | None = None
    gen_out: GeneratorOutput | None = None
    verify_outcome = None
    readme_md = ""
    build_ok = False
    build_err: str | None = None
    forbidden_result: security.StaticAnalysisResult | None = None

    for attempt in (1, 2):
        try:
            gen_out = generator.generate(
                archetype="tracker",
                prompt=prompt,
                source_url=item.url,
                source_headline=item.headline,
                source_summary=item.summary,
                previous_build_error=build_err,
                app_id=app_id,
            )
        except generator.GeneratorJSONError as exc:
            log.warning("%s: generator JSON error: %s", app_id, exc)
            break
        verify_outcome = verify.verify(gen_out, app_id=app_id)
        readme_md = readme_writer.write(
            app_name=app_id,
            prompt=prompt,
            archetype="tracker",
            source_headline=item.headline,
            app_id=app_id,
        )
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
        work = _stage_chassis(
            chassis_dir,
            page_tsx=verify_outcome.output.page_tsx,
            data_ts=verify_outcome.output.data_ts,
            readme_md=readme_md,
        )

        # Static analysis: hard policy gate. No retry on failure.
        sa = security.static_analysis(
            {
                "app/page.tsx": verify_outcome.output.page_tsx,
                "lib/data.ts": verify_outcome.output.data_ts,
            },
            archetype="tracker",
        )
        if not sa.safe:
            log.warning("%s: static analysis stillborn (attempt %d): %s", app_id, attempt, sa.reason)
            forbidden_result = sa
            break

        ok, output = _run_next_build(work)
        if ok:
            build_ok = True
            log.info("%s: build ok (attempt %d)", app_id, attempt)
            break
        log.warning("%s: build failed (attempt %d): %s", app_id, attempt, output[:300])
        build_err = output

    if forbidden_result is not None:
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds())
        db.insert_app(AppRecord(
            id=app_id, prompt=prompt, archetype="tracker",
            archetype_score=m.scores.tracker,
            tied_archetypes=m.selected_archetypes if len(m.selected_archetypes) > 1 else None,
            source="news",
            source_metadata={"url": item.url, "headline": item.headline, "feed": item.feed_source},
            status="stillborn", death_cause="forbidden_pattern",
            generation_seconds=elapsed,
            verifier_verdict=(verify_outcome.verdict if verify_outcome else None),
            verifier_notes=(verify_outcome.notes if verify_outcome else None),
        ))
        audit.event(
            audit.ORCHESTRATOR, "app.stillborn", target=app_id,
            reason=f"forbidden_pattern: {forbidden_result.reason}",
        )
        db.upsert_news_cache(url=item.url, headline=item.headline, feed_source=item.feed_source,
                             published_at=item.published_at, guard_status="passed",
                             matched_archetype="tracker", matcher_score=m.scores.tracker,
                             resulted_in_app=app_id)
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
        return "stillborn_forbidden"

    if not build_ok or gen_out is None or verify_outcome is None:
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds())
        db.insert_app(AppRecord(
            id=app_id, prompt=prompt, archetype="tracker",
            archetype_score=m.scores.tracker,
            tied_archetypes=m.selected_archetypes if len(m.selected_archetypes) > 1 else None,
            source="news",
            source_metadata={"url": item.url, "headline": item.headline, "feed": item.feed_source},
            status="stillborn", death_cause="never_built",
            generation_seconds=elapsed,
            verifier_verdict=(verify_outcome.verdict if verify_outcome else None),
            verifier_notes=(verify_outcome.notes if verify_outcome else None),
        ))
        audit.event(audit.ORCHESTRATOR, "app.stillborn", target=app_id, reason="never_built (build failure after retry)")
        db.upsert_news_cache(url=item.url, headline=item.headline, feed_source=item.feed_source,
                             published_at=item.published_at, guard_status="passed",
                             matched_archetype="tracker", matcher_score=m.scores.tracker,
                             resulted_in_app=app_id)
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
        return "stillborn_build"

    assert work is not None  # mypy
    # 4. GitHub publish (fake commit history)
    try:
        publish_result = github_publish.publish(
            name=app_id,
            description=f"{item.headline} (Vibe Mill {datetime.now(timezone.utc):%Y-%m-%d})",
            src=work,
        )
    except Exception as exc:
        log.error("%s: github publish failed: %s", app_id, exc)
        db.insert_app(AppRecord(
            id=app_id, prompt=prompt, archetype="tracker",
            archetype_score=m.scores.tracker, source="news",
            source_metadata={"url": item.url, "headline": item.headline, "feed": item.feed_source},
            status="stillborn", death_cause="never_built",
            verifier_verdict=verify_outcome.verdict, verifier_notes=verify_outcome.notes,
        ))
        audit.event(audit.ORCHESTRATOR, "app.stillborn", target=app_id, reason=f"github publish failed: {exc}")
        shutil.rmtree(work, ignore_errors=True)
        return "stillborn_publish"

    # 5. Vercel deploy (auto-fires on push; we just create the project + poll)
    deploy_result = None
    try:
        vercel_deploy.create_project_for_repo(app_id)
        deploy_result = vercel_deploy.wait_for_url(app_id)
    except Exception as exc:
        log.error("%s: vercel deploy failed: %s", app_id, exc)
        # Per OPERATIONS.md: stillborn but archive GitHub repo
        try:
            from .clients import github
            github.archive_repo(app_id)
        except Exception as exc2:
            log.warning("%s: github archive after vercel failure also failed: %s", app_id, exc2)
        db.insert_app(AppRecord(
            id=app_id, prompt=prompt, archetype="tracker",
            archetype_score=m.scores.tracker, source="news",
            source_metadata={"url": item.url, "headline": item.headline, "feed": item.feed_source},
            github_url=publish_result.html_url,
            status="stillborn", death_cause="never_built",
            verifier_verdict=verify_outcome.verdict, verifier_notes=verify_outcome.notes,
        ))
        audit.event(audit.ORCHESTRATOR, "app.stillborn", target=app_id, reason=f"vercel deploy failed: {exc}")
        shutil.rmtree(work, ignore_errors=True)
        return "stillborn_deploy"

    # 6. Screenshot (failure is non-fatal)
    screenshot_path: str | None = None
    screenshot_status = "missing"
    try:
        shot = screenshot.capture(app_id=app_id, url=deploy_result.public_url)
        screenshot_path = supabase.upload_screenshot(app_id, shot.jpeg_bytes)
        screenshot_status = "captured"
    except Exception as exc:
        log.warning("%s: screenshot/upload failed (shipping anyway): %s", app_id, exc)

    elapsed = int((datetime.now(timezone.utc) - started).total_seconds())

    # 7. Insert the final app row
    db.insert_app(AppRecord(
        id=app_id, prompt=prompt, archetype="tracker",
        archetype_score=m.scores.tracker,
        tied_archetypes=m.selected_archetypes if len(m.selected_archetypes) > 1 else None,
        github_url=publish_result.html_url,
        vercel_url=deploy_result.public_url,
        screenshot_path=screenshot_path,
        screenshot_status=screenshot_status,
        generation_seconds=elapsed,
        source="news",
        source_metadata={"url": item.url, "headline": item.headline, "feed": item.feed_source},
        status="live",
        verifier_verdict=verify_outcome.verdict,
        verifier_notes=verify_outcome.notes,
    ))
    db.upsert_news_cache(url=item.url, headline=item.headline, feed_source=item.feed_source,
                         published_at=item.published_at, guard_status="passed",
                         matched_archetype="tracker", matcher_score=m.scores.tracker,
                         resulted_in_app=app_id)
    audit.event(audit.ORCHESTRATOR, "app.create", target=app_id,
                reason=f"shipped from news (verdict={verify_outcome.verdict})")

    shutil.rmtree(work, ignore_errors=True)
    log.info("%s: shipped -> %s", app_id, deploy_result.public_url)
    return "shipped" if screenshot_status == "captured" else "screenshot_missing"


# ============================================================================
# Cron tick
# ============================================================================


def run_tick() -> TickResult:
    settings = get_settings()
    cap = settings.DAILY_COST_CAP_USD
    spent = db.today_cost_usd()
    if spent >= cap:
        log.error("daily cost cap exceeded: spent=$%.4f cap=$%.4f; aborting tick", spent, cap)
        audit.event(audit.ORCHESTRATOR, "tick.abort", reason=f"cost cap: $%.4f >= $%.4f" % (spent, cap))
        return TickResult(0, 0, 0, skipped_cost_cap=True)
    log.info("tick start: today_cost=$%.4f cap=$%.4f", spent, cap)

    items = ingest.fetch_new_items()
    if not items:
        log.info("tick: no new items")
        return TickResult(0, 0, 0, skipped_cost_cap=False)

    shipped = 0
    rejections = 0
    stillborn = 0
    for item in items:
        if shipped >= MAX_APPS_PER_TICK:
            log.info("tick: hit MAX_APPS_PER_TICK=%d, deferring rest to next tick", MAX_APPS_PER_TICK)
            break
        try:
            outcome = _ship_one(item)
        except Exception as exc:
            log.exception("unexpected error processing %s: %s", item.url, exc)
            continue
        if outcome.startswith("rejected"):
            rejections += 1
        elif outcome.startswith("stillborn"):
            stillborn += 1
        else:
            shipped += 1
        # Re-check cost cap mid-loop in case generator burned through budget
        if db.today_cost_usd() >= cap:
            log.error("daily cost cap hit mid-tick; stopping")
            break

    try:
        snapshot.push()
    except Exception as exc:
        log.warning("tick: snapshot push failed (will retry next tick): %s", exc)

    log.info("tick done: shipped=%d rejections=%d stillborn=%d", shipped, rejections, stillborn)
    return TickResult(shipped, rejections, stillborn, skipped_cost_cap=False)


def _configure_logging() -> None:
    level = getattr(logging, get_settings().LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    _configure_logging()
    if args:
        # Subcommand: dispatch to the click CLI.
        from . import cli  # local import to avoid click overhead on cron path
        return cli.cli.main(args=args, standalone_mode=False, prog_name="vibemill") or 0
    run_tick()
    return 0


if __name__ == "__main__":
    sys.exit(main())
