"""Determinism sweep: every built-in scenario run twice, compare_runs must return no diffs.

Short durations (<=4 s) keep the suite fast; scenarios marked slow run at full catalog duration.
MP4 scenario (S16) is skipped (no file) and produces a NOT_RUN record rather than crashing.
"""

from __future__ import annotations

import pytest

from skylock.benchmark.catalog import builtin_scenarios
from skylock.benchmark.compare import compare_runs
from skylock.benchmark.runner import BenchmarkRunner
from skylock.config.presets import spec_default

# Scenarios that should be run at full duration (mark as slow)
_SLOW_SCENARIO_IDS = {
    "S05_line_spec_noise",
    "S06_jitter20",
    "S07_platform20",
    "S13_all_disturbances",
}

# Short duration override for fast scenarios (seconds)
_SHORT_DURATION_S = 4.0

_ALL_SCENARIOS = {s.id: s for s in builtin_scenarios()}


def _get_marker(scenario_id: str) -> list:
    if scenario_id in _SLOW_SCENARIO_IDS:
        return [pytest.mark.slow]
    return []


def _determinism_params():
    """Yield (scenario_id, marks) for parametrize."""
    for sid in _ALL_SCENARIOS:
        marks = _get_marker(sid)
        yield pytest.param(sid, marks=marks, id=sid)


@pytest.mark.parametrize("scenario_id", list(_determinism_params()))
def test_determinism_run_twice(scenario_id: str) -> None:
    """Running the same scenario+seed twice must yield compare_runs with no diffs."""
    scenario = _ALL_SCENARIOS[scenario_id]
    seed = scenario.seeds[0]

    # S16_mp4 has no path — expect a NOT_RUN record without crashing
    if scenario.input_kind == "mp4" and not scenario.mp4_path:
        runner = BenchmarkRunner(spec_default())
        record = runner.run(scenario, seed)
        assert record.status in ("not_run", "NOT_RUN", "skipped"), (
            f"S16 without mp4_path should produce a not-run record, got status={record.status!r}"
        )
        return

    base_cfg = spec_default()
    runner = BenchmarkRunner(base_cfg)

    # Override duration for non-slow scenarios
    from dataclasses import replace as dc_replace

    if scenario_id not in _SLOW_SCENARIO_IDS:
        scenario = dc_replace(scenario, duration_s=_SHORT_DURATION_S)

    record_a = runner.run(scenario, seed)
    record_b = runner.run(scenario, seed)

    diffs = compare_runs(record_a, record_b)

    assert not diffs, (
        f"[{scenario_id}] Determinism violation — {len(diffs)} diff(s) found:\n"
        + "\n".join(f"  {d.field}: {d.value_a!r} != {d.value_b!r} ({d.reason})" for d in diffs)
    )


@pytest.mark.parametrize("scenario_id", list(_determinism_params()))
def test_determinism_frame_count_consistent(scenario_id: str) -> None:
    """Both runs must process the same number of frames."""
    scenario = _ALL_SCENARIOS[scenario_id]
    seed = scenario.seeds[0]

    if scenario.input_kind == "mp4" and not scenario.mp4_path:
        pytest.skip("S16 has no mp4_path — skipping frame count check")

    base_cfg = spec_default()
    runner = BenchmarkRunner(base_cfg)

    from dataclasses import replace as dc_replace

    if scenario_id not in _SLOW_SCENARIO_IDS:
        scenario = dc_replace(scenario, duration_s=_SHORT_DURATION_S)

    record_a = runner.run(scenario, seed)
    record_b = runner.run(scenario, seed)

    assert record_a.frames == record_b.frames, (
        f"[{scenario_id}] Frame counts differ: {record_a.frames} vs {record_b.frames}"
    )
