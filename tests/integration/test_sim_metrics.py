"""Integration test running simulation with scripted occlusion window to verify

reacquisition metric.
"""

from __future__ import annotations

from skylock.app.session import Session
from skylock.config.models import (
    CameraConfig,
    LineMotion,
    SkyLockConfig,
    TargetConfig,
    TargetSetConfig,
)
from skylock.core.enums import MetricStatus
from skylock.metrics.collector import MetricsCollector


def test_sim_run_with_scripted_occlusion_measures_reacquisition() -> None:
    """Run closed-loop simulation with an occlusion window and verify reacquisition is measured."""
    # Target starts at origin (in FOV), moves slowly, occluded from t=0.5 to t=0.8 s
    target = TargetConfig(
        initial="fixed",
        initial_pos_deg=(0.0, 0.0),
        motion=LineMotion(speed_deg_s=0.0, heading_deg=0.0),
        visibility_windows=((0.5, 0.8),),
    )
    cfg = SkyLockConfig(
        camera=CameraConfig(fps=30.0),
        target=TargetSetConfig(count=1, targets=(target,)),
        seed=42,
    )

    collector = MetricsCollector(cfg)
    session = Session(config=cfg, collector=collector)

    # Run for 1.5 seconds (45 frames)
    # Frames 0 to 14 (0.0 to 0.467s): tracked
    # Frames 15 to 24 (0.5 to 0.8s): occluded -> tracker loses target
    # Frames 25 to 44 (0.833 to 1.467s): target reappears -> tracker re-acquires
    session.run(seconds=1.5)

    metrics = collector.finalize()

    # Verify basic acquisition
    assert metrics.acquisition_time_from_start_s.status == MetricStatus.MEASURED
    assert metrics.acquisition_time_from_observable_s.status == MetricStatus.MEASURED
    assert metrics.successful_acquisition.status == MetricStatus.MEASURED
    assert metrics.successful_acquisition.value is True

    # Verify reacquisition event was triggered and measured under ground_truth basis
    assert metrics.reacquisition_time_s.status == MetricStatus.MEASURED
    assert metrics.reacquisition_time_s.value is not None
    assert metrics.reacquisition_time_s.value.n >= 1
    assert metrics.reacquisition_time_s.value.basis == "ground_truth"
    assert metrics.reacquisition_time_s.value.mean_s >= 0.0
    assert metrics.successful_reacquisition.status == MetricStatus.MEASURED

    # Verify tracking and pointing errors are measured
    assert metrics.tracking_error_px.status == MetricStatus.MEASURED
    assert metrics.pointing_error_px.status == MetricStatus.MEASURED
    assert metrics.centering_error_px.status == MetricStatus.MEASURED
