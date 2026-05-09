"""Pytest wrapper around vibemill.smoke_test.

This calls into the runnable smoke module so `pytest` and
`python -m vibemill.smoke_test` exercise the same code path.

The test hits real OpenRouter (cost: ~$0.01-0.05) and runs npm install +
next build (~30-60s). It is excluded from normal pytest runs unless
explicitly selected:

    pytest tests/test_smoke.py -m smoke

Configure pytest to recognize the marker by adding to pyproject.toml:
    [tool.pytest.ini_options]
    markers = ["smoke: end-to-end LLM + build test (slow, costs money)"]
"""

from __future__ import annotations

import pytest

from vibemill import smoke_test


@pytest.mark.smoke
def test_end_to_end() -> None:
    result = smoke_test.run()
    assert result.guard_decision == "pass"
    assert "tracker" in result.matcher_selected
    assert result.generator_chars > 0
    assert result.build_ok
