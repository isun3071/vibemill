"""End-to-end smoke test for the LLM pipeline + chassis build.

Steps (per GENERATOR.md v2):
1. Load fixed test news fixture
2. Guard (must pass)
3. Matcher (must select Tracker)
4. Generator
5. Verifier
6. JSON validity covered by pydantic parsing
7. Stage chassis + write slot files in a tempdir
8. Run npm install + next build
9. Assert build succeeds

Does NOT push to GitHub, deploy to Vercel, or take a screenshot.
Run via: python -m vibemill.smoke_test  OR  vibemill smoke-test
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from . import db, generator, guard, matcher, readme_writer, verify
from .config import get_settings
from .models import NewsItem

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "test_news.json"
NEXT_BUILD_TIMEOUT_S = 240


class SmokeFailure(RuntimeError):
    pass


@dataclass
class SmokeResult:
    guard_decision: str
    matcher_selected: list[str]
    generator_chars: int
    verifier_verdict: str
    build_ok: bool
    build_seconds: int
    workdir: Path
    cost_usd: float


def _load_fixture() -> NewsItem:
    data = json.loads(FIXTURE_PATH.read_text())
    return NewsItem(
        url=data["url"],
        headline=data["headline"],
        summary=data["summary"],
        feed_source=data["feed_source"],
        published_at=None,
    )


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


def run(*, keep_workdir: bool = False) -> SmokeResult:
    settings = get_settings()
    cost_before = db.today_cost_usd()
    item = _load_fixture()
    prompt = f"{item.headline}. {item.summary}".strip()

    log.info("smoke: 1/9 guard")
    g = guard.check(prompt, app_id="smoke")
    if g.decision != "pass":
        raise SmokeFailure(f"guard rejected fixture: {g.reason}")

    log.info("smoke: 2/9 matcher")
    m = matcher.score(prompt, app_id="smoke")
    if m is None:
        raise SmokeFailure("matcher returned None (parse failures)")
    log.info("smoke: matcher scores=%s selected=%s", m.scores.as_dict(), m.selected_archetypes)
    if "tracker" not in m.selected_archetypes:
        raise SmokeFailure(
            f"fixture did not select tracker; selected={m.selected_archetypes!r} "
            f"scores={m.scores.as_dict()}"
        )

    log.info("smoke: 5/9 readme (single LLM call, independent of slot files)")
    readme = readme_writer.write(
        app_name="smoke-test-tracker",
        prompt=prompt,
        archetype="tracker",
        source_headline=item.headline,
        app_id="smoke",
    )

    chassis = settings.archetypes_dir / "tracker" / "chassis"
    work: Path | None = None
    build_seconds = 0
    v_out = None
    build_err: str | None = None

    # generator -> verifier -> stage -> build, with one retry on build failure.
    # Mirrors __main__._ship_one() so the smoke test exercises the same
    # resilience the production pipeline has.
    for attempt in (1, 2):
        log.info("smoke: 3/9 generator (attempt %d)", attempt)
        gen = generator.generate(
            archetype="tracker",
            prompt=prompt,
            source_url=item.url,
            source_headline=item.headline,
            source_summary=item.summary,
            previous_build_error=build_err,
            app_id="smoke",
        )

        log.info("smoke: 4/9 verifier (attempt %d)", attempt)
        v_out = verify.verify(gen, app_id="smoke")
        log.info("smoke: verifier verdict=%r", v_out.verdict)

        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
        log.info("smoke: 6/9 stage chassis -> tempdir (attempt %d)", attempt)
        work = _stage(chassis, page_tsx=v_out.output.page_tsx, data_ts=v_out.output.data_ts, readme_md=readme)

        log.info("smoke: 7/9 npm install + next build (attempt %d, workdir=%s)", attempt, work)
        started = time.monotonic()
        ok, output = _build(work)
        build_seconds = int(time.monotonic() - started)
        if ok:
            log.info("smoke: 8/9 build ok in %ds (attempt %d)", build_seconds, attempt)
            break
        log.warning("smoke: build failed on attempt %d in %ds:\n%s", attempt, build_seconds, output[:600])
        build_err = output
    else:
        if not keep_workdir and work is not None:
            shutil.rmtree(work, ignore_errors=True)
        raise SmokeFailure(f"build failed after {build_seconds}s on retry:\n{build_err}")

    assert v_out is not None and work is not None  # mypy: loop ran at least once
    v = v_out

    if not keep_workdir:
        shutil.rmtree(work, ignore_errors=True)

    cost_after = db.today_cost_usd()
    log.info("smoke: 9/9 done; total cost=$%.4f", cost_after - cost_before)

    return SmokeResult(
        guard_decision=g.decision,
        matcher_selected=m.selected_archetypes,
        generator_chars=len(v.output.page_tsx) + len(v.output.data_ts),
        verifier_verdict=v.verdict,
        build_ok=True,
        build_seconds=build_seconds,
        workdir=work,
        cost_usd=cost_after - cost_before,
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    try:
        result = run()
    except SmokeFailure as exc:
        print(f"SMOKE TEST FAILED: {exc}", file=sys.stderr)
        return 1
    print("SMOKE TEST PASSED")
    print(f"  guard: {result.guard_decision}")
    print(f"  matcher selected: {result.matcher_selected}")
    print(f"  verifier verdict: {result.verifier_verdict}")
    print(f"  generator output: {result.generator_chars} chars")
    print(f"  build: ok in {result.build_seconds}s")
    print(f"  total cost: ${result.cost_usd:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
