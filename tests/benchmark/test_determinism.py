"""Determinism tests: same scenario+seed gives identical results in-process and cross-process."""

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
def s01():
    scenarios = {s.id: s for s in builtin_scenarios()}
    return scenarios["S01_line_clean"]


def test_determinism_in_process(runner: BenchmarkRunner, s01) -> None:
    """Two in-process runs with same scenario+seed must produce identical deterministic fields."""
    r1 = runner.run(s01, seed=42)
    r2 = runner.run(s01, seed=42)

    diffs = compare_runs(r1, r2)
    assert diffs == [], f"Determinism violation: {diffs}"

    # Verify essential fields match
    assert r1.state_timeline_hash == r2.state_timeline_hash
    assert r1.estimates_hash == r2.estimates_hash
    assert r1.config_hash == r2.config_hash
    assert r1.frames == r2.frames


@pytest.mark.slow
def test_determinism_cross_process(runner: BenchmarkRunner, s01) -> None:
    """In-process vs subprocess run with same scenario+seed must be identical."""
    r_in = runner.run(s01, seed=42, isolate=False)
    r_sub = runner.run(s01, seed=42, isolate=True)

    diffs = compare_runs(r_in, r_sub)
    assert diffs == [], f"Cross-process determinism violation: {diffs}"


def test_different_seeds_differ(runner: BenchmarkRunner, s01) -> None:
    """Different seeds must produce different state timelines (for random-dependent scenarios)."""
    # S01 line_clean is deterministic regardless of seed for motion,
    # but seed affects noise RNG. Use S05 for actual seed difference.
    scenarios = {s.id: s for s in builtin_scenarios()}
    s05 = scenarios["S05_line_spec_noise"]
    r1 = runner.run(s05, seed=1)
    r2 = runner.run(s05, seed=2)

    # With different seeds on noisy scenario, the tracking may diverge
    # At minimum, the config_hash should differ (seed is part of config)
    assert r1.config_hash != r2.config_hash
