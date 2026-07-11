"""Unit tests for the pure eval comparison/regression logic (testing-strategy §4.3).

These are fast, I/O-free tests for ``app.evals.comparison`` (U-13..U-17). The
DB-bound orchestration that calls ``classify_change`` is covered by the
integration test ``test_compare_latest_complete_version_runs_flags_regressions``
in ``test_phase5_evals.py`` (I-27).
"""

from __future__ import annotations

import pytest

from app.evals.comparison import (
    CHANGE_IMPROVEMENT,
    CHANGE_REGRESSION,
    CHANGE_UNCHANGED,
    classify_change,
    compute_pass_rate,
)


def test_classify_change_flags_regression() -> None:
    """U-13: version A passes case X, version B fails case X -> regression."""
    assert classify_change(passed_a=True, passed_b=False) == CHANGE_REGRESSION


def test_classify_change_flags_improvement() -> None:
    """U-14: version A fails case X, version B passes case X -> improvement."""
    assert classify_change(passed_a=False, passed_b=True) == CHANGE_IMPROVEMENT


def test_classify_change_both_pass_is_unchanged() -> None:
    """U-15: both pass -> not in regressions or improvements."""
    assert classify_change(passed_a=True, passed_b=True) == CHANGE_UNCHANGED


def test_classify_change_both_fail_is_unchanged() -> None:
    """U-16: both fail -> not in regressions or improvements."""
    assert classify_change(passed_a=False, passed_b=False) == CHANGE_UNCHANGED


def test_aggregate_pass_rate_delta_b_worse() -> None:
    """U-17: aggregate pass rate A=5/6, B=2/6 -> delta < 0, B worse.

    The API returns a *rate-based* delta (pass_rate_b - pass_rate_a), so
    5/6 vs 2/6 yields a delta of approximately -0.5 (not a count-based -3).
    The load-bearing assertion is the sign and relative ordering: B is worse.
    """
    rate_a = compute_pass_rate(passed_count=5, total_cases=6)
    rate_b = compute_pass_rate(passed_count=2, total_cases=6)
    delta = rate_b - rate_a

    assert rate_a == pytest.approx(5 / 6)
    assert rate_b == pytest.approx(2 / 6)
    assert delta < 0, "B should be worse than A"
    assert delta == pytest.approx(-0.5, abs=0.01)


def test_compute_pass_rate_zero_cases_is_zero() -> None:
    """Edge case: zero total cases must not raise (returns 0.0)."""
    assert compute_pass_rate(passed_count=0, total_cases=0) == 0.0


def test_compute_pass_rate_full_pass_is_one() -> None:
    """Edge case: all cases pass -> 1.0."""
    assert compute_pass_rate(passed_count=6, total_cases=6) == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
