"""Statistical verification of model_rotation.pick_generator.

Rolls pick_generator 1000 times against the configured pool and confirms
the observed frequency of each slug is within 2.5 binomial standard
deviations of the configured weight. Cheap (no LLM calls), runs in <1s.

Use to verify the picker behaves correctly after editing GENERATOR_MODELS,
GENERATOR_WEIGHTS, or GENERATOR_REASONING_EFFORTS in .env.

Run from repo root:
    python scripts/verify_rotation.py
"""

from __future__ import annotations

import math
import random
import sys
from collections import Counter

from rich.console import Console
from rich.table import Table

from vibemill import model_rotation

N_ROLLS = 1000
TOLERANCE_SIGMAS = 2.5  # ~99% confidence the picker matches its configured weights


def main() -> int:
    console = Console()
    try:
        pool = model_rotation.parse_pool()
    except model_rotation.ModelRotationError as exc:
        console.print(f"[red]pool config invalid: {exc}[/red]")
        return 1

    rng = random.Random()  # local rng so the test is reproducible if needed
    counts: Counter[str] = Counter()
    for _ in range(N_ROLLS):
        choice = model_rotation.pick_generator(pool, rng=rng)
        counts[choice.slug] += 1

    console.print(f"[dim]rolled {N_ROLLS} picks against the configured pool[/dim]\n")

    table = Table(title="Distribution check")
    table.add_column("slug")
    table.add_column("effort")
    table.add_column("expected", justify="right")
    table.add_column("observed", justify="right")
    table.add_column("diff", justify="right")
    table.add_column("±2.5σ", justify="right")
    table.add_column("ok")

    failures = 0
    for choice, weight in zip(pool.choices, pool.weights):
        expected = N_ROLLS * weight
        observed = counts[choice.slug]
        std = math.sqrt(N_ROLLS * weight * (1 - weight))
        bound = TOLERANCE_SIGMAS * std
        diff = abs(observed - expected)
        within = diff <= bound
        if not within:
            failures += 1
        table.add_row(
            choice.slug,
            choice.reasoning_effort,
            f"{expected:.1f}",
            str(observed),
            f"{diff:+.1f}",
            f"±{bound:.1f}",
            "[green]✓[/green]" if within else "[red]✗[/red]",
        )

    console.print(table)
    console.print()

    if failures:
        console.print(f"[red]{failures}/{len(pool.choices)} slugs outside tolerance[/red]")
        console.print("[dim]picker may not be honoring weights; investigate.[/dim]")
        return 1
    console.print(f"[green]all {len(pool.choices)} slugs within ±{TOLERANCE_SIGMAS}σ of expected[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
