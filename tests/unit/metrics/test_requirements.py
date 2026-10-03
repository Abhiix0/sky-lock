"""Unit tests for requirement evaluation and tri-state verdict rules."""

from __future__ import annotations

from skylock.config.models import RequirementsConfig
from skylock.core.enums import Verdict
from skylock.metrics.requirements import evaluate
from skylock.metrics.status import (
    ErrorStats,
    Metric,
    ReacquisitionSummary,
    RunMetrics,
)


def _make_passing_metrics() -> RunMetrics:
    """Construct synthetic metrics satisfying all requirements."""
    return RunMetrics(
        metrics_version="1",
        total_frames=100,
        observable_duration_s=5.0,
        acquisition_time_from_start_s=Metric.measured(0.8),
        acquisition_time_from_observable_s=Metric.measured(0.5),  # <= 2.0s
        successful_acquisition=Metric.measured(True),
        tracking_error_px=Metric.measured(
            ErrorStats(mean=4.0, rms=5.0, p95=7.0, max=8.0, n=80)  # rms <= 10.0
        ),
        pointing_error_px=Metric.measured(
            ErrorStats(mean=3.0, rms=4.0, p95=6.0, max=7.0, n=80)
        ),
        centering_error_px=Metric.measured(
            ErrorStats(mean=2.0, rms=3.0, p95=4.0, max=5.0, n=80)
        ),
        reacquisition_time_s=Metric.measured(
            ReacquisitionSummary(
                events=(),
                mean_s=0.4,
                max_s=0.6,  # <= 1.0s
                n=1,
                basis="ground_truth",
            )
        ),
        successful_reacquisition=Metric.measured(True),
        target_loss_rate=Metric.measured(0.02),  # < 0.05
        lock_retention=Metric.measured(0.98),
        detection_rate=Metric.measured(0.95),
        detection_present_rate=Metric.measured(0.99),
        fps_pipeline=Metric.measured(45.0),  # >= 20.0
        fps_wall=Metric.measured(40.0),
    )


def test_evaluate_all_pass() -> None:
    """When all metrics are MEASURED and satisfy thresholds, overall verdict is PASS."""
    metrics = _make_passing_metrics()
    req = RequirementsConfig()

    verdicts = evaluate(metrics, req)
    assert verdicts["acquisition_time"] == Verdict.PASS
    assert verdicts["tracking_error"] == Verdict.PASS
    assert verdicts["target_loss_rate"] == Verdict.PASS
    assert verdicts["reacquisition_time"] == Verdict.PASS
    assert verdicts["processing_fps"] == Verdict.PASS
    assert verdicts["overall"] == Verdict.PASS


def test_evaluate_fail_dominates() -> None:
    """If any metric exceeds threshold, requirement is FAIL and overall is FAIL."""
    metrics = RunMetrics(
        metrics_version="1",
        total_frames=100,
        observable_duration_s=5.0,
        acquisition_time_from_observable_s=Metric.measured(3.5),  # FAIL (> 2.0s)
        tracking_error_px=Metric.measured(
            ErrorStats(mean=4.0, rms=5.0, p95=7.0, max=8.0, n=80)
        ),
        target_loss_rate=Metric.measured(0.01),
        reacquisition_time_s=Metric.not_run("No loss"),  # INDETERMINATE
        fps_pipeline=Metric.measured(35.0),
    )
    req = RequirementsConfig()

    verdicts = evaluate(metrics, req)
    assert verdicts["acquisition_time"] == Verdict.FAIL
    assert verdicts["tracking_error"] == Verdict.PASS
    assert verdicts["reacquisition_time"] == Verdict.INDETERMINATE
    assert verdicts["overall"] == Verdict.FAIL


def test_evaluate_indeterminate_never_pass() -> None:
    """If some metrics are non-MEASURED and none FAIL, overall is INDETERMINATE (never PASS)."""
    metrics = RunMetrics(
        metrics_version="1",
        total_frames=100,
        observable_duration_s=5.0,
        acquisition_time_from_observable_s=Metric.measured(0.5),  # PASS
        tracking_error_px=Metric.not_run("No GT"),  # INDETERMINATE
        target_loss_rate=Metric.measured(0.01),  # PASS
        reacquisition_time_s=Metric.not_run("No loss"),  # INDETERMINATE
        fps_pipeline=Metric.measured(35.0),  # PASS
    )
    req = RequirementsConfig()

    verdicts = evaluate(metrics, req)
    assert verdicts["tracking_error"] == Verdict.INDETERMINATE
    assert verdicts["overall"] == Verdict.INDETERMINATE


def test_special_acquisition_rule_full_observable_fails() -> None:
    """Rule: acquisition is FAIL (not INDETERMINATE) when observable duration >= acquisition_max_s

    and tracker never reached TRACK.
    """
    metrics = RunMetrics(
        metrics_version="1",
        total_frames=100,
        observable_duration_s=3.0,  # >= 2.0s acquisition_max_s
        acquisition_time_from_observable_s=Metric.not_acquired("Never acquired"),
        acquisition_time_from_start_s=Metric.not_acquired("Never acquired"),
        tracking_error_px=Metric.not_acquired("Never in track"),
        target_loss_rate=Metric.not_acquired("Never in track"),
        reacquisition_time_s=Metric.not_run("No loss event"),
        fps_pipeline=Metric.measured(30.0),
    )
    req = RequirementsConfig(acquisition_max_s=2.0)

    verdicts = evaluate(metrics, req)
    assert verdicts["acquisition_time"] == Verdict.FAIL
    assert verdicts["overall"] == Verdict.FAIL


def test_special_acquisition_rule_short_observable_indeterminate() -> None:
    """If run was shorter than acquisition_max_s and never acquired, verdict is INDETERMINATE."""
    metrics = RunMetrics(
        metrics_version="1",
        total_frames=15,
        observable_duration_s=0.5,  # < 2.0s acquisition_max_s
        acquisition_time_from_observable_s=Metric.not_acquired("Never acquired"),
        acquisition_time_from_start_s=Metric.not_acquired("Never acquired"),
        tracking_error_px=Metric.not_acquired("Never in track"),
        target_loss_rate=Metric.not_acquired("Never in track"),
        reacquisition_time_s=Metric.not_run("No loss event"),
        fps_pipeline=Metric.measured(30.0),
    )
    req = RequirementsConfig(acquisition_max_s=2.0)

    verdicts = evaluate(metrics, req)
    assert verdicts["acquisition_time"] == Verdict.INDETERMINATE
    assert verdicts["overall"] == Verdict.INDETERMINATE
