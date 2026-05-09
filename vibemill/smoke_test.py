"""End-to-end smoke test for the LLM pipeline + chassis build.

Fixture-driven: each fixture in tests/fixtures/test_news*.json carries
its own `expected_outcome`, and the test asserts that branch was taken
without raising on the rejection paths.

Outcomes the smoke test recognises:
- happy_path: guard pass, tracker selected, build_ok=True
- guard_reject: guard returns reject (short-circuits; no matcher call)
- matcher_reject: guard pass, matcher returns selected_archetypes=[]
- non_tracker_archetype: guard pass, matcher selects something other
  than tracker (V0 only ships Tracker; orchestrator would log the
  rejection with reason 'archetype not yet implemented')

Per ANTI_PATTERNS rule 8 the guard and matcher are separate calls.
Per GENERATOR.md v3 the static analysis is a hard gate between verify
and build, no retry; the build step gets one retry on failure.

Does NOT push to GitHub, deploy to Vercel, or take a screenshot.
Run via:
  python -m vibemill.smoke_test                 # all four fixtures
  python -m vibemill.smoke_test --fixture NAME  # one fixture
  vibemill smoke-test [--fixture NAME]
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import db, generator, guard, matcher, model_rotation, readme_writer, security, verify
from .config import get_settings
from .models import NewsItem

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
NEXT_BUILD_TIMEOUT_S = 240
COST_SANITY_CAP_USD = 0.10

# All bundled smoke fixtures, in the order the CLI runs them.
DEFAULT_FIXTURES: tuple[str, ...] = (
    "test_news.json",
    "test_news_guard_reject.json",
    "test_news_matcher_reject.json",
    "test_news_non_tracker.json",
)

OUTCOME_HAPPY = "happy_path"
OUTCOME_GUARD_REJECT = "guard_reject"
OUTCOME_MATCHER_REJECT = "matcher_reject"
OUTCOME_NON_TRACKER = "non_tracker_archetype"


class SmokeFailure(RuntimeError):
    pass


@dataclass
class SmokeResult:
    fixture: str
    expected_outcome: str
    outcome: str = ""
    outcome_matched: bool = False
    guard_decision: str = ""
    matcher_selected: list[str] = field(default_factory=list)
    generator_chars: int = 0
    verifier_verdict: str = ""
    static_analysis_safe: bool | None = None
    build_ok: bool | None = None
    build_seconds: int = 0
    workdir: Path | None = None
    cost_usd: float = 0.0
    notes: str = ""


def _load_fixture(name: str) -> tuple[NewsItem, str]:
    path = FIXTURE_DIR / name
    data = json.loads(path.read_text())
    item = NewsItem(
        url=data["url"],
        headline=data["headline"],
        summary=data["summary"],
        feed_source=data.get("feed_source", "fixture"),
        published_at=None,
    )
    expected = data.get("expected_outcome", OUTCOME_HAPPY)
    return item, expected


def _stage(chassis: Path, *, page_tsx: str, data_ts: str, readme_md: str) -> Path:
    work = Path(tempfile.mkdtemp(prefix="vibemill-smoke-"))
    shutil.copytree(chassis, work, dirs_exist_ok=True)
    (work / "app" / "page.tsx").write_text(page_tsx)
    (work / "lib" / "data.ts").write_text(data_ts)
    (work / "README.md").write_text(readme_md or "")
    return work


def _build(work: Path) -> tuple[bool, str]:
    install = subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund", "--silent"],
        cwd=work, capture_output=True, text=True, timeout=NEXT_BUILD_TIMEOUT_S,
    )
    if install.returncode != 0:
        return False, install.stderr[-1500:]
    build = subprocess.run(
        ["npx", "--yes", "next", "build"],
        cwd=work, capture_output=True, text=True, timeout=NEXT_BUILD_TIMEOUT_S,
    )
    if build.returncode != 0:
        return False, build.stdout[-1500:] + "\n---\n" + build.stderr[-500:]
    return True, build.stdout[-300:]


def _run_happy_pipeline(
    item: NewsItem,
    *,
    keep_workdir: bool,
    result: SmokeResult,
) -> None:
    """Generator -> verifier -> static analysis -> stage -> build, with one
    retry on build failure. Mutates `result` in place. Raises SmokeFailure on
    static-analysis stillborn or build retry exhaustion."""
    settings = get_settings()
    chassis = settings.archetypes_dir / "tracker" / "chassis"
    prompt = f"{item.headline}. {item.summary}".strip()
    fixture = result.fixture

    # Use the first pool member for reproducibility of the smoke test. Real
    # rotation distribution is verified by scripts/verify_rotation.py
    # (statistical) and by manual end-to-end runs.
    pool = model_rotation.parse_pool()
    smoke_model = pool.choices[0]
    log.info("[%s] using model=%s reasoning=%s", fixture, smoke_model.slug, smoke_model.reasoning_effort)

    log.info("[%s] 5/10 readme", fixture)
    readme = readme_writer.write(
        app_name="smoke-test-tracker",
        prompt=prompt,
        archetype="tracker",
        source_headline=item.headline,
        model=smoke_model,
        app_id=f"smoke-{fixture}",
    )

    work: Path | None = None
    build_seconds = 0
    v_out = None
    build_err: str | None = None

    for attempt in (1, 2):
        log.info("[%s] 3/10 generator (attempt %d)", fixture, attempt)
        gen = generator.generate(
            archetype="tracker",
            prompt=prompt,
            source_url=item.url,
            source_headline=item.headline,
            source_summary=item.summary,
            previous_build_error=build_err,
            model=smoke_model,
            app_id=f"smoke-{fixture}",
        )

        log.info("[%s] 4/10 verifier (attempt %d)", fixture, attempt)
        v_out = verify.verify(gen, model=smoke_model, app_id=f"smoke-{fixture}")
        log.info("[%s] verifier verdict=%r", fixture, v_out.verdict)

        log.info("[%s] 6/10 static analysis (attempt %d)", fixture, attempt)
        sa = security.static_analysis(
            {"app/page.tsx": v_out.output.page_tsx, "lib/data.ts": v_out.output.data_ts},
            archetype="tracker",
        )
        result.static_analysis_safe = sa.safe
        if not sa.safe:
            if work is not None and not keep_workdir:
                shutil.rmtree(work, ignore_errors=True)
            raise SmokeFailure(f"static analysis stillborn: {sa.reason}")

        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
        log.info("[%s] 7/10 stage chassis (attempt %d)", fixture, attempt)
        work = _stage(chassis, page_tsx=v_out.output.page_tsx, data_ts=v_out.output.data_ts, readme_md=readme)

        log.info("[%s] 8/10 npm install + next build (attempt %d)", fixture, attempt)
        started = time.monotonic()
        ok, output = _build(work)
        build_seconds = int(time.monotonic() - started)
        if ok:
            log.info("[%s] 9/10 build ok in %ds (attempt %d)", fixture, build_seconds, attempt)
            break
        log.warning("[%s] build failed on attempt %d in %ds:\n%s", fixture, attempt, build_seconds, output[:600])
        build_err = output
    else:
        if not keep_workdir and work is not None:
            shutil.rmtree(work, ignore_errors=True)
        raise SmokeFailure(f"build failed after {build_seconds}s on retry:\n{build_err}")

    assert v_out is not None and work is not None
    if not keep_workdir:
        shutil.rmtree(work, ignore_errors=True)

    result.verifier_verdict = v_out.verdict
    result.generator_chars = len(v_out.output.page_tsx) + len(v_out.output.data_ts)
    result.build_ok = True
    result.build_seconds = build_seconds
    result.workdir = work


def run_one(fixture_name: str, *, keep_workdir: bool = False) -> SmokeResult:
    """Run one fixture through the pipeline, classify the outcome, return the
    result. Raises SmokeFailure only on infrastructure failures (build retry
    exhausted, static analysis stillborn on a happy_path fixture, etc.).
    Outcome mismatches set outcome_matched=False but do not raise.
    """
    item, expected = _load_fixture(fixture_name)
    cost_before = db.today_cost_usd()
    result = SmokeResult(fixture=fixture_name, expected_outcome=expected)
    prompt = f"{item.headline}. {item.summary}".strip()

    log.info("[%s] 1/10 guard (expected=%s)", fixture_name, expected)
    g = guard.check(prompt, app_id=f"smoke-{fixture_name}")
    result.guard_decision = g.decision

    if g.decision == "reject":
        result.outcome = OUTCOME_GUARD_REJECT
        result.outcome_matched = (expected == OUTCOME_GUARD_REJECT)
        result.notes = f"guard reason: {g.reason}"
        result.cost_usd = db.today_cost_usd() - cost_before
        return result

    log.info("[%s] 2/10 matcher", fixture_name)
    m = matcher.score(prompt, app_id=f"smoke-{fixture_name}")
    if m is None:
        # Treat parse failure as matcher_reject since the orchestrator does
        # the equivalent (logs a rejection with reason 'matcher_error').
        result.outcome = OUTCOME_MATCHER_REJECT
        result.outcome_matched = (expected == OUTCOME_MATCHER_REJECT)
        result.notes = "matcher parse failure"
        result.cost_usd = db.today_cost_usd() - cost_before
        return result

    result.matcher_selected = m.selected_archetypes
    log.info("[%s] matcher selected=%s", fixture_name, m.selected_archetypes)

    if not m.selected_archetypes:
        result.outcome = OUTCOME_MATCHER_REJECT
        result.outcome_matched = (expected == OUTCOME_MATCHER_REJECT)
        best = m.scores.best()
        result.notes = f"no archetype above threshold; best={best[0]}/{best[1]}"
        result.cost_usd = db.today_cost_usd() - cost_before
        return result

    if "tracker" not in m.selected_archetypes:
        # Matcher picked something but not tracker; in V0 the orchestrator
        # would log this as 'archetype not yet implemented' and reject.
        result.outcome = OUTCOME_NON_TRACKER
        result.outcome_matched = (expected == OUTCOME_NON_TRACKER)
        result.notes = f"selected={m.selected_archetypes}"
        result.cost_usd = db.today_cost_usd() - cost_before
        return result

    # Happy path: tracker is in selected. Run the full build pipeline.
    if expected != OUTCOME_HAPPY:
        log.warning(
            "[%s] expected=%s but matcher selected tracker; running happy pipeline anyway",
            fixture_name, expected,
        )
    _run_happy_pipeline(item, keep_workdir=keep_workdir, result=result)
    result.outcome = OUTCOME_HAPPY
    result.outcome_matched = (expected == OUTCOME_HAPPY)

    cost = db.today_cost_usd() - cost_before
    result.cost_usd = cost
    if cost >= COST_SANITY_CAP_USD:
        log.warning("[%s] cost $%.4f exceeded sanity cap $%.4f", fixture_name, cost, COST_SANITY_CAP_USD)
    log.info("[%s] 10/10 done; cost=$%.4f outcome=%s matched=%s",
             fixture_name, cost, result.outcome, result.outcome_matched)
    return result


def run_all(*, keep_workdir: bool = False) -> list[SmokeResult]:
    return [run_one(name, keep_workdir=keep_workdir) for name in DEFAULT_FIXTURES]


# Backward-compat shim for the old single-fixture API.
def run(fixture: str = "test_news.json", *, keep_workdir: bool = False) -> SmokeResult:
    return run_one(fixture, keep_workdir=keep_workdir)


def _print_result(r: SmokeResult) -> None:
    status = "PASS" if r.outcome_matched else "FAIL"
    print(f"[{status}] {r.fixture}")
    print(f"    expected: {r.expected_outcome}    got: {r.outcome}")
    print(f"    guard: {r.guard_decision}    matcher: {r.matcher_selected or '-'}")
    if r.outcome == OUTCOME_HAPPY:
        print(f"    verifier: {r.verifier_verdict}    static: {'ok' if r.static_analysis_safe else 'FAIL'}    build: {'ok' if r.build_ok else 'FAIL'} in {r.build_seconds}s")
    if r.notes:
        print(f"    notes: {r.notes}")
    print(f"    cost: ${r.cost_usd:.4f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the LLM pipeline + chassis build")
    parser.add_argument("--fixture", help="Fixture filename under tests/fixtures/ (default: run all)")
    parser.add_argument("--keep", action="store_true", help="Leave the temp build dir on disk")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    if args.fixture:
        try:
            result = run_one(args.fixture, keep_workdir=args.keep)
        except SmokeFailure as exc:
            print(f"SMOKE TEST FAILED [{args.fixture}]: {exc}", file=sys.stderr)
            return 1
        _print_result(result)
        return 0 if result.outcome_matched else 1

    failures = 0
    for name in DEFAULT_FIXTURES:
        try:
            r = run_one(name, keep_workdir=args.keep)
        except SmokeFailure as exc:
            print(f"SMOKE TEST FAILED [{name}]: {exc}", file=sys.stderr)
            failures += 1
            continue
        _print_result(r)
        if not r.outcome_matched:
            failures += 1
    print(f"\n{len(DEFAULT_FIXTURES) - failures}/{len(DEFAULT_FIXTURES)} fixtures passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
