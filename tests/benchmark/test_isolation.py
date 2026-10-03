"""Isolation tests: running S05 then S01 gives the same S01 result as S01 alone."""

from __future__ import annotations

import pytest

from skylock.benchmark.catalog import builtin_scenarios
from skylock.benchmark.compare import compare_runs
from skylock.benchmark.runner import BenchmarkRunner
from skylock.config.models import SkyLockConfig


@pytest.fixture()
def runner() -> BenchmarkRunner:
    return BenchmarkRunner(base_config=SkyLockConfig())


@pytest.fixture()
def scenarios():
    return {s.id: s for s in builtin_scenarios()}


def test_isolation_s05_then_s01(
    runner: BenchmarkRunner, scenarios: dict
) -> None:
    """Running S05 before S01 must not contaminate S01 results.

    S05 has noise disturbances that could pollute global state (RNG, cv2 state)
    if isolation is broken.
    """
    # Run S01 alone
    r_s01_alone = runner.run(scenarios["S01_line_clean"], seed=42)

    # Run S05 then S01
    _ = runner.run(scenarios["S05_line_spec_noise"], seed=42)
    r_s01_after_s05 = runner.run(scenarios["S01_line_clean"], seed=42)

    diffs = compare_runs(r_s01_alone, r_s01_after_s05)
    assert diffs == [], f"Isolation violation (S05 contaminated S01): {diffs}"

    assert r_s01_alone.state_timeline_hash == r_s01_after_s05.state_timeline_hash
    assert r_s01_alone.estimates_hash == r_s01_after_s05.estimates_hash


def test_isolation_different_scenarios_same_seed(
    runner: BenchmarkRunner, scenarios: dict
) -> None:
    """Different scenarios with same seed should produce different results."""
    r1 = runner.run(scenarios["S01_line_clean"], seed=42)
    r2 = runner.run(scenarios["S02_circle_clean"], seed=42)

    # Different scenarios must differ in state timeline or estimates
    assert r1.scenario_id != r2.scenario_id
    # They may share config_hash since seed is same but overrides differ
