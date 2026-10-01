"""Unit tests for Metric[T] invariant and status contracts."""

from __future__ import annotations

import json

import pytest

from skylock.core.enums import MetricStatus
from skylock.metrics.status import (
    ErrorStats,
    LatencyStats,
    Metric,
    MissedFrames,
    ReacquisitionEvent,
    ReacquisitionSummary,
    RunMetrics,
)


def test_metric_invariant_measured() -> None:
    """Invariant: MEASURED status must have non-None, non-NaN value."""
    m = Metric.measured(10.5)
    assert m.status == MetricStatus.MEASURED
    assert m.value == 10.5
    assert m.reason is None

    # Cannot instantiate MEASURED with None
    with pytest.raises(ValueError, match="cannot be None when status is MEASURED"):
        Metric(value=None, status=MetricStatus.MEASURED)

    # measured() factory rejects None
    with pytest.raises(ValueError, match="requires a non-None value"):
        Metric.measured(None)  # type: ignore[arg-type]

    # measured() factory rejects NaN
    with pytest.raises(ValueError, match="cannot accept NaN"):
        Metric.measured(float("nan"))


def test_metric_invariant_non_measured() -> None:
    """Invariant: Non-MEASURED status must have value is None."""
    for factory, status in [
        (Metric.not_run, MetricStatus.NOT_RUN),
        (Metric.not_acquired, MetricStatus.NOT_ACQUIRED),
        (Metric.failed, MetricStatus.FAILED),
    ]:
        m = factory("test reason")
        assert m.status == status
        assert m.value is None
        assert m.reason == "test reason"

        # Direct instantiation with non-None value must raise
        with pytest.raises(ValueError, match="must be None when status is"):
            Metric(value=42.0, status=status, reason="bad")


def test_metric_json_serialization_emits_null() -> None:
    """Serializing non-MEASURED metric must emit null, never NaN or 0."""
    m_not_run = Metric.not_run("Prerequisite not met")
    d = m_not_run.as_dict()
    assert d["value"] is None
    assert d["status"] == "NOT_RUN"
    assert d["reason"] == "Prerequisite not met"

    serialized = json.dumps(d)
    assert '"value": null' in serialized
    assert "NaN" not in serialized

    m_measured = Metric.measured(12.5)
    d_meas = m_measured.as_dict()
    assert d_meas["value"] == 12.5
    assert d_meas["status"] == "MEASURED"


def test_error_stats_as_dict() -> None:
    """ErrorStats serialization integrity."""
    stats = ErrorStats(mean=2.5, rms=3.0, p95=4.0, max=5.0, n=100)
    d = stats.as_dict()
    assert d == {"mean": 2.5, "rms": 3.0, "p95": 4.0, "max": 5.0, "n": 100}


def test_latency_stats_as_dict() -> None:
    """LatencyStats serialization integrity."""
    stats = LatencyStats(mean=1.5, p50=1.2, p95=2.0, max=3.5, n=50)
    d = stats.as_dict()
    assert d == {"mean": 1.5, "p50": 1.2, "p95": 2.0, "max": 3.5, "n": 50}


def test_reacquisition_summary_as_dict() -> None:
    """ReacquisitionSummary serialization integrity."""
    ev = ReacquisitionEvent(
        duration_s=0.5,
        basis="ground_truth",
        success=True,
        t_start=1.0,
        t_end=1.5,
    )
    summary = ReacquisitionSummary(
        events=(ev,),
        mean_s=0.5,
        max_s=0.5,
        n=1,
        basis="ground_truth",
    )
    d = summary.as_dict()
    assert d["mean_s"] == 0.5
    assert d["n"] == 1
    assert len(d["events"]) == 1
    assert d["events"][0]["duration_s"] == 0.5


def test_missed_frames_as_dict() -> None:
    """MissedFrames serialization integrity."""
    missed = MissedFrames(processing_missed=2, source_dropped=1, total_frames=100)
    assert missed.as_dict() == {
        "processing_missed": 2,
        "source_dropped": 1,
        "total_frames": 100,
    }


def test_run_metrics_defaults_and_as_dict() -> None:
    """RunMetrics default construction and dictionary representation."""
    metrics = RunMetrics()
    assert metrics.metrics_version == "1"
    assert metrics.total_frames == 0
    assert metrics.acquisition_time_from_start_s.status == MetricStatus.NOT_RUN

    d = metrics.as_dict()
    assert d["metrics_version"] == "1"
    assert d["total_frames"] == 0
    assert d["acquisition_time_from_start_s"]["status"] == "NOT_RUN"
    assert d["acquisition_time_from_start_s"]["value"] is None
