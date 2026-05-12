"""End-to-end smoke test for the LLM pipeline + chassis build.

Fixture-driven: each fixture in tests/fixtures/test_news*.json carries
its own `expected_outcome`, and the test asserts that branch was taken
without raising on the rejection paths.

Bundle G's synthetic-prompt pipeline (the 60% non-news path) is NOT
covered by smoke fixtures — synthetic prompts are LLM-generated per
tick and non-reproducible. To exercise that path, run a live tick:
`python -m vibemill`. The orchestrator rolls 40/60 news/synthetic and
will exercise both paths.

Outcomes the smoke test recognises:
- happy_path: guard pass, tracker selected, build_ok=True
- guard_reject: guard returns reject (short-circuits; no matcher call)
- matcher_reject: guard pass, matcher returns selected_archetypes=[]
- non_tracker_archetype: guard pass, matcher selects an archetype
  outside the buildable set (orchestrator would log the rejection
  with reason 'archetype not yet implemented'). Bundle F: buildable
  set is tracker, chatbot, utility_tool, search_directory.

Per ANTI_PATTERNS rule 8 the guard and matcher are separate calls.
Per GENERATOR.md v3 the static analysis is a hard gate between verify
and build, no retry; the build step gets one retry on failure.

Does NOT push to GitHub, deploy to Vercel, or take a screenshot.
Run via:
  python -m vibemill.smoke_test                       # all four fixtures, dashboard layout
  python -m vibemill.smoke_test --fixture NAME        # one fixture
  python -m vibemill.smoke_test --layout map_dominant # pin a different layout
  vibemill smoke-test [--fixture NAME] [--layout NAME]
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

from . import db, generator, guard, layouts, matcher, model_rotation, readme_writer, security, verify
from .config import get_settings
from .models import NewsItem

DEFAULT_SMOKE_LAYOUT = "dashboard"  # most-weighted layout, modal output

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
NEXT_BUILD_TIMEOUT_S = 240
COST_SANITY_CAP_USD = 0.10

# All bundled smoke fixtures, in the order the CLI runs them.
# Bundle H: test_news_ai_generator.json exercises the Python rail end-to-end
# (generator, verifier, static analysis, ast-parse build proxy) without
# actually pushing to HF Spaces or GitHub.
DEFAULT_FIXTURES: tuple[str, ...] = (
    "test_news.json",
    "test_news_guard_reject.json",
    "test_news_matcher_reject.json",
    "test_news_non_tracker.json",
    "test_news_ai_generator.json",
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


def _extract_yaml_frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    return text[: end + len("\n---")]


def _stage(chassis: Path, *, files: list, readme_md: str) -> Path:
    """Bundle D: write the LLM's full file list into a fresh chassis copy.

    Bundle H: preserve HF Spaces YAML frontmatter from the chassis README;
    persona content goes after it. Matches __main__._stage_chassis logic so
    smoke and production stay aligned.
    """
    work = Path(tempfile.mkdtemp(prefix="vibemill-smoke-"))
    shutil.copytree(chassis, work, dirs_exist_ok=True)
    for f in files:
        out_path = work / f.path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(f.content)
    readme_path = work / "README.md"
    existing = readme_path.read_text() if readme_path.exists() else ""
    fm = _extract_yaml_frontmatter(existing)
    if fm:
        readme_path.write_text(f"{fm}\n\n{readme_md or ''}")
    else:
        readme_path.write_text(readme_md or "")
    return work


def _build(work: Path, archetype: str) -> tuple[bool, str]:
    """Substrate-aware build proxy. JS: npm install + next build.
    Python (Bundle H): ast.parse(app.py) for a cheap syntax check; HF
    Spaces validates the rest at deploy time, which smoke skips."""
    from .models import SUBSTRATE_BY_ARCHETYPE
    if SUBSTRATE_BY_ARCHETYPE.get(archetype) == "python":
        import ast
        app_py = work / "app.py"
        if not app_py.is_file():
            return False, "no app.py at the root of the working directory"
        try:
            ast.parse(app_py.read_text())
        except SyntaxError as exc:
            return False, f"app.py syntax error: {exc}"
        return True, "app.py parses cleanly"

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
    archetype: str,
    layout: str | None,
) -> None:
    """Generator -> verifier -> static analysis -> stage -> build, with one
    retry on build failure. Mutates `result` in place. Raises SmokeFailure on
    static-analysis stillborn or build retry exhaustion.

    Bundle F: archetype is the matcher's pick (must be in the buildable set);
    layout is the tracker layout name when archetype=='tracker', else None
    (other archetypes don't have layout sub-templates yet).
    """
    settings = get_settings()
    chassis = settings.archetypes_dir / archetype / "chassis"
    prompt = f"{item.headline}. {item.summary}".strip()
    fixture = result.fixture

    # Bundle E: single substrate. Pin to mean_good's effort for smoke
    # reproducibility (the tier itself is pinned to mean_good below).
    smoke_model = model_rotation.generator_model_for_tier("mean_good")
    log.info("[%s] using model=%s reasoning=%s archetype=%s layout=%s",
             fixture, smoke_model.slug, smoke_model.reasoning_effort, archetype, layout)

    # Pin persona to enthusiastic for reproducibility (the actual rotation
    # distribution is tested separately via 1000-roll statistical check).
    smoke_persona = "enthusiastic"
    log.info("[%s] 5/10 readme persona=%s", fixture, smoke_persona)
    readme = readme_writer.write(
        app_name=f"smoke-test-{archetype}",
        prompt=prompt,
        archetype=archetype,
        source_headline=item.headline,
        model=smoke_model,
        persona=smoke_persona,
        app_id=f"smoke-{fixture}",
    )

    work: Path | None = None
    build_seconds = 0
    v_out = None
    build_err: str | None = None

    for attempt in (1, 2):
        log.info("[%s] 3/10 generator (attempt %d, archetype=%s, layout=%s)",
                 fixture, attempt, archetype, layout)
        gen = generator.generate(
            archetype=archetype,
            prompt=prompt,
            source_url=item.url,
            source_headline=item.headline,
            source_summary=item.summary,
            previous_build_error=build_err,
            tier="mean_good",  # smoke pins to mean_good (modal output)
            layout=layout,  # tracker only; other archetypes pass None
            model=smoke_model,
            app_id=f"smoke-{fixture}",
        )

        log.info("[%s] 4/10 verifier (attempt %d)", fixture, attempt)
        v_out = verify.verify(gen, archetype=archetype, model=smoke_model, app_id=f"smoke-{fixture}")
        log.info("[%s] verifier verdict=%r files=%d", fixture, v_out.verdict, len(v_out.output.files))

        log.info("[%s] 6/10 static analysis (attempt %d)", fixture, attempt)
        sa = security.static_analysis(
            {f.path: f.content for f in v_out.output.files},
        )
        result.static_analysis_safe = sa.safe
        if not sa.safe:
            if work is not None and not keep_workdir:
                shutil.rmtree(work, ignore_errors=True)
            raise SmokeFailure(f"static analysis stillborn: {sa.reason}")

        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
        log.info("[%s] 7/10 stage chassis (attempt %d, %d files)", fixture, attempt, len(v_out.output.files))
        work = _stage(chassis, files=v_out.output.files, readme_md=readme)

        log.info("[%s] 8/10 build check (attempt %d)", fixture, attempt)
        started = time.monotonic()
        ok, output = _build(work, archetype)
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
    result.generator_chars = sum(len(f.content) for f in v_out.output.files)
    result.build_ok = True
    result.build_seconds = build_seconds
    result.workdir = work


def run_one(
    fixture_name: str,
    *,
    keep_workdir: bool = False,
    layout: str = DEFAULT_SMOKE_LAYOUT,
) -> SmokeResult:
    """Run one fixture through the pipeline, classify the outcome, return the
    result. Raises SmokeFailure only on infrastructure failures (build retry
    exhausted, static analysis stillborn on a happy_path fixture, etc.).
    Outcome mismatches set outcome_matched=False but do not raise.

    `layout` (Bundle C) selects the tracker visual layout to pin. Defaults
    to 'dashboard' (the most-weighted layout). Use other names to verify
    individual layout templates produce buildable apps.
    """
    if layout not in layouts.LAYOUT_NAMES:
        raise ValueError(f"unknown layout '{layout}'; valid: {sorted(layouts.LAYOUT_NAMES)}")
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

    # Bundle F: matcher may pick anything from the 13; orchestrator only
    # ships if the pick lands in the buildable set (tracker / chatbot /
    # utility_tool / search_directory). Mirror that logic here.
    picked = matcher.pick(m)
    if not matcher.is_v0_buildable(picked):
        result.outcome = OUTCOME_NON_TRACKER  # kept for fixture compat
        result.outcome_matched = (expected == OUTCOME_NON_TRACKER)
        result.notes = f"picked={picked}, selected={m.selected_archetypes}"
        result.cost_usd = db.today_cost_usd() - cost_before
        return result

    # Happy path: a buildable archetype was picked. Run the full build
    # pipeline against THAT archetype. Tracker keeps the pinned layout;
    # other archetypes pass None (no layout sub-rotation in Bundle F).
    if expected != OUTCOME_HAPPY:
        log.warning(
            "[%s] expected=%s but matcher picked buildable archetype %s; running happy pipeline anyway",
            fixture_name, expected, picked,
        )
    pipeline_layout = layout if picked == "tracker" else None
    _run_happy_pipeline(
        item,
        keep_workdir=keep_workdir,
        result=result,
        archetype=picked,
        layout=pipeline_layout,
    )
    result.outcome = OUTCOME_HAPPY
    result.outcome_matched = (expected == OUTCOME_HAPPY)

    cost = db.today_cost_usd() - cost_before
    result.cost_usd = cost
    if cost >= COST_SANITY_CAP_USD:
        log.warning("[%s] cost $%.4f exceeded sanity cap $%.4f", fixture_name, cost, COST_SANITY_CAP_USD)
    log.info("[%s] 10/10 done; cost=$%.4f outcome=%s matched=%s",
             fixture_name, cost, result.outcome, result.outcome_matched)
    return result


def run_all(*, keep_workdir: bool = False, layout: str = DEFAULT_SMOKE_LAYOUT) -> list[SmokeResult]:
    return [run_one(name, keep_workdir=keep_workdir, layout=layout) for name in DEFAULT_FIXTURES]


# Backward-compat shim for the old single-fixture API.
def run(
    fixture: str = "test_news.json",
    *,
    keep_workdir: bool = False,
    layout: str = DEFAULT_SMOKE_LAYOUT,
) -> SmokeResult:
    return run_one(fixture, keep_workdir=keep_workdir, layout=layout)


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
    parser.add_argument(
        "--layout",
        default=DEFAULT_SMOKE_LAYOUT,
        choices=sorted(layouts.LAYOUT_NAMES),
        help=f"Tracker layout to pin (default: {DEFAULT_SMOKE_LAYOUT})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    if args.fixture:
        try:
            result = run_one(args.fixture, keep_workdir=args.keep, layout=args.layout)
        except SmokeFailure as exc:
            print(f"SMOKE TEST FAILED [{args.fixture}]: {exc}", file=sys.stderr)
            return 1
        _print_result(result)
        return 0 if result.outcome_matched else 1

    failures = 0
    for name in DEFAULT_FIXTURES:
        try:
            r = run_one(name, keep_workdir=args.keep, layout=args.layout)
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
