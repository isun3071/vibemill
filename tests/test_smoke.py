"""Pytest wrapper around vibemill.smoke_test.

Parametrized: each bundled fixture is its own test case so a failure
points at the specific rejection path that broke. All four hit real
OpenRouter (~$0.04 total) and one fixture runs npm install + next build
(~30-60s). Excluded from default pytest runs unless explicitly selected:

    pytest tests/test_smoke.py -m smoke

The marker is registered in pyproject.toml.
"""

from __future__ import annotations

import pytest

from vibemill import smoke_test


@pytest.mark.smoke
@pytest.mark.parametrize("fixture", list(smoke_test.DEFAULT_FIXTURES))
def test_fixture(fixture: str) -> None:
    result = smoke_test.run_one(fixture)
    assert result.outcome_matched, (
        f"{fixture}: expected={result.expected_outcome} got={result.outcome} "
        f"(notes: {result.notes})"
    )
    assert result.cost_usd < smoke_test.COST_SANITY_CAP_USD, (
        f"{fixture}: cost ${result.cost_usd:.4f} exceeded sanity cap "
        f"${smoke_test.COST_SANITY_CAP_USD:.2f}"
    )
    if result.outcome == smoke_test.OUTCOME_HAPPY:
        assert result.matcher_selected, "happy_path: matcher_selected must be non-empty"
        assert result.build_ok is True
        assert result.static_analysis_safe is True
