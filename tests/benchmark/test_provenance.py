"""Provenance tests: all required fields present in RunRecord."""

from __future__ import annotations

import pytest

from skylock.benchmark.catalog import builtin_scenarios
from skylock.benchmark.runner import BenchmarkRunner
from skylock.config.models import SkyLockConfig


@pytest.fixture()
def runner() -> BenchmarkRunner:
    return BenchmarkRunner(base_config=SkyLockConfig())


@pytest.fixture()
def s01():
    return next(s for s in builtin_scenarios() if s.id == "S01_line_clean")


_REQUIRED_FIELDS = (
    "run_id",
    "scenario_id",
    "seed",
    "software_version",
    "python_version",
    "numpy_version",
    "opencv_version",
    "platform_info",
    "config_snapshot",
    "config_hash",
    "input_source",
    "duration_s",
    "frames",
    "metrics",
    "verdicts",
    "overall_verdict",
    "started_at_utc",
    "wall_time_s",
    "git_commit",
    "status",
    "state_timeline_hash",
    "estimates_hash",
)


def test_all_provenance_fields_present(runner: BenchmarkRunner, s01) -> None:
    """Every RunRecord must contain all required provenance fields."""
    record = runner.run(s01, seed=42)

    record_dict = record.as_dict()
    for field_name in _REQUIRED_FIELDS:
        assert field_name in record_dict, f"Missing provenance field: {field_name}"


def test_provenance_types(runner: BenchmarkRunner, s01) -> None:
    """Provenance fields must have correct types."""
    record = runner.run(s01, seed=42)

    assert isinstance(record.run_id, str) and len(record.run_id) > 0
    assert record.scenario_id == "S01_line_clean"
    assert record.seed == 42
    assert isinstance(record.software_version, str)
    assert isinstance(record.python_version, str)
    assert isinstance(record.numpy_version, str)
    assert isinstance(record.opencv_version, str)
    assert isinstance(record.platform_info, str)
    assert isinstance(record.config_snapshot, dict)
    assert isinstance(record.config_hash, str) and len(record.config_hash) == 64
    assert record.input_source == "simulation"
    assert isinstance(record.duration_s, float)
    assert isinstance(record.frames, int) and record.frames > 0
    assert isinstance(record.metrics, dict)
    assert isinstance(record.verdicts, dict)
    assert isinstance(record.overall_verdict, str)
    assert isinstance(record.started_at_utc, str)
    assert isinstance(record.wall_time_s, float) and record.wall_time_s >= 0
    assert record.git_commit is None or isinstance(record.git_commit, str)
    assert record.status == "COMPLETED"
    assert isinstance(record.state_timeline_hash, str)
    assert isinstance(record.estimates_hash, str)


def test_mp4_not_run_provenance(runner: BenchmarkRunner) -> None:
    """Missing MP4 produces NOT_RUN record, not crash and not zeros."""
    s16 = next(s for s in builtin_scenarios() if s.id == "S16_mp4")
    record = runner.run(s16, seed=1)

    assert record.status == "NOT_RUN"
    assert record.overall_verdict == "NOT_RUN"
    assert record.frames == 0
    assert record.error is not None
    # Provenance still populated
    assert isinstance(record.software_version, str)
    assert isinstance(record.platform_info, str)
