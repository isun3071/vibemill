"""Statistical verification of tiers.pick_tier.

Rolls pick_tier 1000 times against the configured weights and confirms
each tier's observed frequency is within 2.5 binomial standard
deviations of the configured weight. Cheap (no LLM/search calls), runs
in <1s.

Use to verify the picker behaves correctly after editing
vibemill/tiers.py:TIER_WEIGHTS.

Run from repo root:
    python scripts/verify_tier_distribution.py
"""

from __future__ import annotations

import math
import random
import sys
from collections import Counter

from rich.console import Console
from rich.table import Table

from vibemill import tiers

N_ROLLS = 1000
TOLERANCE_SIGMAS = 2.5  # ~99% confidence the picker matches its configured weights


def main() -> int:
    console = Console()
    rng = random.Random()
    counts: Counter[str] = Counter()
    for _ in range(N_ROLLS):
        counts[tiers.pick_tier(rng=rng)] += 1

    console.print(f"[dim]rolled {N_ROLLS} tier picks against the configured weights[/dim]\n")

    table = Table(title="Tier distribution")
    table.add_column("tier")
    table.add_column("expected", justify="right")
    table.add_column("observed", justify="right")
    table.add_column("diff", justify="right")
    table.add_column("±2.5σ", justify="right")
    table.add_column("ok")

    failures = 0
    for tier, weight in tiers.TIER_WEIGHTS:
        expected = N_ROLLS * weight
        observed = counts[tier]
        std = math.sqrt(N_ROLLS * weight * (1 - weight))
        bound = TOLERANCE_SIGMAS * std
        diff = abs(observed - expected)
        within = diff <= bound
        if not within:
            failures += 1
        table.add_row(
            tier,
            f"{expected:.1f}",
            str(observed),
            f"{diff:+.1f}",
            f"±{bound:.1f}",
            "[green]✓[/green]" if within else "[red]✗[/red]",
        )

    console.print(table)
    console.print()

    if failures:
        console.print(f"[red]{failures}/{len(tiers.TIER_WEIGHTS)} tiers outside tolerance[/red]")
        return 1
    console.print(f"[green]all {len(tiers.TIER_WEIGHTS)} tiers within ±{TOLERANCE_SIGMAS}σ of expected[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
