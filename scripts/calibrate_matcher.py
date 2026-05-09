"""Offline calibration for the guard + matcher pipeline.

Runs the live prompts against a fixed test set, prints a Rich table, dumps
the full per-input result to data/calibration_runs/{ISO}.json, diffs against
the most recent prior run.

Use this after touching prompts/guard.txt or prompts/matcher.txt to verify
the scoring distribution and rejection posture have not drifted. Per
ANTI_PATTERNS.md rule 8, the two stages are deliberately separated; this
script keeps that separation and does not combine them into one LLM call.

Cost: ~$0.005 per fixture x 15 = ~$0.08 per run. Latency: ~30 seconds.

Run from repo root, inside the venv:
    python scripts/calibrate_matcher.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from vibemill import db, guard, matcher
from vibemill.config import get_settings

log = logging.getLogger(__name__)
console = Console()


# Fifteen fixtures: 12 archetype-targeted (one per archetype) + 3 edge cases.
# Most are drawn from MATCHER.md's calibration list; a few are synthesized
# where MATCHER.md's example would have been guard-rejected (e.g. Hantavirus
# with a fatality, which the guard correctly flags as exploitative).
FIXTURES: list[dict[str, str]] = [
    # 12 archetype hits
    {
        "id": "tracker_pure",
        "headline": "EPA releases Q1 2026 air quality dashboard for 50 US metros",
        "summary": "Particulate readings rose in 18 of 50 cities tracked. The new dashboard publishes weekly per-city PM2.5 averages and ranks regions by year-over-year change. Coverage extends through Q4 2026.",
        "expected": "tracker",
    },
    {
        "id": "parody_ui_emails",
        "headline": "DOJ releases full Epstein email archive in searchable form",
        "summary": "Approximately 47,000 messages spanning 2001-2018 between named correspondents are now public. Senders include public-figure recipients across finance, politics, and academia.",
        "expected": "parody_ui",
    },
    {
        "id": "case_file_uap",
        "headline": "Defense Department releases UAP files spanning four decades",
        "summary": "Rolling release of redacted incident reports, witness statements, radar transcripts. New batches each Friday through year end. Files include classification metadata and analyst annotations.",
        "expected": "case_file_browser",
    },
    {
        "id": "counter_67",
        "headline": "Why students keep saying '67' to nothing in particular",
        "summary": "The two-digit phrase has spread through middle and high schools nationwide with no agreed meaning. Teachers report it interrupting class as a punctuation mark. Origin remains unclear.",
        "expected": "counter_game",
    },
    {
        "id": "disruption_suez",
        "headline": "Suez Canal blockage cuts container traffic for third day",
        "summary": "A grounded vessel has halted northbound traffic since Tuesday. 200+ ships are queued at both ends. Refiners and retailers are quoting alternate-route premiums on Asia-Europe routes.",
        "expected": "disruption_visualizer",
    },
    {
        "id": "diaspora_airline",
        "headline": "Defunct airline's stranded passengers traced across 14 countries",
        "summary": "When the carrier ceased operations mid-flight last week, 3,200 passengers were rerouted by partner airlines. Travel groups are mapping where each cohort ended up to coordinate refunds.",
        "expected": "diaspora_map",
    },
    {
        "id": "legal_trans_rights",
        "headline": "Trans rights cases proliferate across 27 state legal systems",
        "summary": "Filings in 2026 already exceed all of 2025. Cases range from school policy challenges to insurance coverage disputes to ID document standards. Multiple appellate decisions expected by Q3.",
        "expected": "legal_action_tracker",
    },
    {
        "id": "mutual_aid_fema",
        "headline": "FEMA capacity changes leave coastal counties planning local response",
        "summary": "Reduced federal pre-positioning has prompted county emergency managers to formalize neighbor-to-neighbor coordination networks. Twelve counties published gap maps this week.",
        "expected": "mutual_aid_coordinator",
    },
    {
        "id": "wordle_senator",
        "headline": "Daily puzzle: guess the senator from their voting record",
        "summary": "A new browser game presents one US senator per day. Players guess by name; the game reveals attribute hints (party, state, committee) on each wrong guess. Streak counter persists.",
        "expected": "wordle_redux",
    },
    {
        "id": "todo_hurricane",
        "headline": "What to pack: hurricane preparedness checklist for coastal residents",
        "summary": "FEMA-aligned checklist of items to assemble in a 72-hour go-bag. Categories: documents, medications, food, water, communication. Personal additions encouraged.",
        "expected": "glorified_todo",
    },
    {
        "id": "social_uap_researchers",
        "headline": "Independent UAP researchers want a dedicated forum",
        "summary": "After a decade on general-purpose social media, civilian UAP investigators are calling for a niche space. Topics: case sharing, FOIA coordination, witness interview transcripts.",
        "expected": "glorified_social",
    },
    {
        "id": "rec_country_to_flee",
        "headline": "Quiz: which country should you flee to based on your politics",
        "summary": "A multi-step preference form (immigration policy, healthcare model, climate, language) returns one recommended destination with a one-paragraph rationale citing the matching attributes.",
        "expected": "recommendation_engine",
    },
    # 3 edge cases
    {
        "id": "edge_guard_reject",
        "headline": "Hantavirus outbreak on cruise ship MV Hondius confirms first fatality",
        "summary": "A passenger has died and twelve cases are confirmed aboard the vessel currently anchored in the South Pacific. Public health agencies in five countries are tracing returning passengers.",
        "expected": "guard_reject",
    },
    {
        "id": "edge_matcher_reject",
        "headline": "Pope Leo and Trump tension surfaces at Vatican summit",
        "summary": "Observers note divergent emphases in their public statements over the past month. Neither side has confirmed direct disagreement. Analysts read it as theological rather than political.",
        "expected": "matcher_reject",
    },
    {
        "id": "edge_ambiguous_tied",
        "headline": "Strait of Hormuz tanker traffic disrupted by escalating tensions",
        "summary": "Daily tanker transits have dropped 35 percent over two weeks following maritime incidents. Insurers are quoting elevated war-risk premiums. Refineries in five Asian markets are publishing contingency schedules.",
        "expected": "ambiguous_tied",
    },
]


def _calibration_dir() -> Path:
    d = get_settings().repo_root / "data" / "calibration_runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _classify_outcome(
    g_decision: str,
    selected: list[str] | None,
    picked: str | None,
) -> str:
    if g_decision == "reject":
        return "guard_reject"
    if not selected:
        return "matcher_reject"
    if selected and len(selected) > 1:
        return "ambiguous_tied"
    return picked or "matcher_reject"


def _matched(expected: str, outcome: str, selected: list[str] | None) -> bool:
    if expected == outcome:
        return True
    # If the expected archetype tied with another and the matcher returned
    # multiple, count that as a match too.
    if outcome == "ambiguous_tied" and selected and expected in selected:
        return True
    return False


def run_one(fixture: dict[str, str]) -> dict[str, Any]:
    cost_before = db.today_cost_usd()
    started = time.perf_counter()
    prompt = f"{fixture['headline']}. {fixture['summary']}".strip()

    g = guard.check(prompt, app_id=f"calib-{fixture['id']}")

    result: dict[str, Any] = {
        "id": fixture["id"],
        "expected": fixture["expected"],
        "headline": fixture["headline"],
        "guard_decision": g.decision,
        "guard_reason": g.reason,
        "best_archetype": None,
        "best_score": None,
        "all_scores": None,
        "selected_archetypes": None,
        "picked": None,
    }

    if g.decision == "reject":
        outcome = "guard_reject"
    else:
        m = matcher.score(prompt, app_id=f"calib-{fixture['id']}")
        if m is None:
            outcome = "matcher_error"
        else:
            best_arch, best_score = m.scores.best()
            picked = matcher.pick(m)
            result.update(
                best_archetype=best_arch,
                best_score=best_score,
                all_scores=m.scores.as_dict(),
                selected_archetypes=m.selected_archetypes,
                picked=picked,
            )
            outcome = _classify_outcome(g.decision, m.selected_archetypes, picked)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    cost = db.today_cost_usd() - cost_before
    result.update(
        outcome=outcome,
        matched=_matched(fixture["expected"], outcome, result["selected_archetypes"]),
        total_cost_usd=cost,
        total_latency_ms=elapsed_ms,
    )
    return result


def render_results_table(results: list[dict[str, Any]]) -> Table:
    table = Table(title="Calibration results", show_lines=False)
    table.add_column("id", style="bold")
    table.add_column("expected")
    table.add_column("outcome")
    table.add_column("best", justify="right")
    table.add_column("score", justify="right")
    table.add_column("ok")
    table.add_column("cost", justify="right")
    table.add_column("ms", justify="right")
    for r in results:
        ok = "[green]✓[/green]" if r["matched"] else "[red]✗[/red]"
        score = "" if r["best_score"] is None else str(r["best_score"])
        table.add_row(
            r["id"],
            r["expected"],
            r["outcome"],
            r["best_archetype"] or "",
            score,
            ok,
            f"${r['total_cost_usd']:.4f}",
            str(r["total_latency_ms"]),
        )
    return table


def render_summary(results: list[dict[str, Any]]) -> Table:
    total = len(results)
    matched = sum(1 for r in results if r["matched"])
    guard_rejects = sum(1 for r in results if r["outcome"] == "guard_reject")
    matcher_rejects = sum(1 for r in results if r["outcome"] == "matcher_reject")
    total_cost = sum(r["total_cost_usd"] for r in results)
    total_latency_s = sum(r["total_latency_ms"] for r in results) / 1000.0

    # Distribution of selected archetypes (for inputs that reached the matcher
    # AND scored at least one archetype above threshold)
    archetype_counts: dict[str, int] = {}
    for r in results:
        for a in (r.get("selected_archetypes") or []):
            archetype_counts[a] = archetype_counts.get(a, 0) + 1
    distribution = ", ".join(f"{a}={n}" for a, n in sorted(archetype_counts.items()))

    table = Table(title="Summary", show_header=False, box=None, padding=(0, 1))
    table.add_row("inputs", f"{total}")
    table.add_row("matched expected", f"{matched}/{total}")
    table.add_row("guard rejection rate", f"{guard_rejects}/{total} ({100*guard_rejects/total:.0f}%)")
    table.add_row("matcher rejection rate", f"{matcher_rejects}/{total} ({100*matcher_rejects/total:.0f}%)")
    table.add_row("total cost", f"${total_cost:.4f}")
    table.add_row("total latency", f"{total_latency_s:.1f}s")
    table.add_row("selected archetypes", distribution or "(none)")
    return table


def find_prior_run(now_iso: str) -> Path | None:
    """Return the JSON path of the most recent calibration run that's not the
    current one. None if no prior run exists."""
    files = sorted((_calibration_dir()).glob("*.json"))
    files = [f for f in files if f.stem != now_iso]
    return files[-1] if files else None


def render_diff(current: list[dict[str, Any]], prior_path: Path) -> Table | None:
    """Return a Rich table of per-input changes vs. the prior run, or None if
    there are no changes."""
    prior_data = json.loads(prior_path.read_text())
    prior_by_id = {r["id"]: r for r in prior_data["results"]}

    rows: list[tuple[str, str, str, str]] = []
    for r in current:
        p = prior_by_id.get(r["id"])
        if p is None:
            rows.append((r["id"], "(new fixture)", "", ""))
            continue
        changes = []
        if p.get("guard_decision") != r["guard_decision"]:
            changes.append(f"guard: {p.get('guard_decision')} → {r['guard_decision']}")
        if p.get("best_archetype") != r["best_archetype"]:
            changes.append(f"best: {p.get('best_archetype')} → {r['best_archetype']}")
        if p.get("best_score") != r["best_score"]:
            changes.append(f"score: {p.get('best_score')} → {r['best_score']}")
        if (p.get("selected_archetypes") or []) != (r.get("selected_archetypes") or []):
            changes.append(
                f"selected: {p.get('selected_archetypes')} → {r['selected_archetypes']}"
            )
        if p.get("outcome") != r["outcome"]:
            changes.append(f"outcome: {p.get('outcome')} → {r['outcome']}")
        if changes:
            rows.append((r["id"], "; ".join(changes), "", ""))

    if not rows:
        return None
    table = Table(title=f"Diff vs. {prior_path.name}", show_header=False, box=None, padding=(0, 1))
    for id_, change, _, _ in rows:
        table.add_row(id_, change)
    return table


def main() -> int:
    logging.basicConfig(
        level=logging.WARNING,  # quiet; the Rich tables are the output
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    console.print(f"[dim]Calibrating against {len(FIXTURES)} fixtures...[/dim]")

    results: list[dict[str, Any]] = []
    for i, f in enumerate(FIXTURES, 1):
        console.print(f"[dim]  [{i}/{len(FIXTURES)}] {f['id']}...[/dim]")
        results.append(run_one(f))

    now = datetime.now(timezone.utc)
    iso = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = _calibration_dir() / f"{iso}.json"
    payload = {
        "ran_at": now.isoformat(),
        "fixture_count": len(FIXTURES),
        "results": results,
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))

    console.print()
    console.print(render_results_table(results))
    console.print()
    console.print(render_summary(results))

    prior = find_prior_run(iso)
    if prior is not None:
        diff = render_diff(results, prior)
        console.print()
        if diff is None:
            console.print(f"[dim]No changes vs. {prior.name}[/dim]")
        else:
            console.print(diff)

    console.print()
    console.print(f"[dim]Saved: {out_path}[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
