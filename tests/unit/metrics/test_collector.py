"""Unit tests for MetricsCollector."""

from __future__ import annotations

import numpy as np

from skylock.config.models import SkyLockConfig
from skylock.core.enums import ControlIntentMode, MetricStatus, TrackState
from skylock.core.types import (
    ControlCommand,
    ControlIntent,
    Frame,
    GroundTruthSample,
    PipelineOutput,
    Pointing,
    StepResult,
    TargetEstimate,
    TargetTruth,
)
from skylock.metrics.collector import MetricsCollector


def _make_step(
    index: int,
    state: TrackState = TrackState.TRACK,
    est_px: tuple[float, float] | None = (320.0, 240.0),
    truth_px: tuple[float, float] | None = (325.0, 240.0),
    latency_ms: float = 10.0,
) -> StepResult:
    frame = Frame(
        image=np.zeros((480, 640), dtype=np.uint8),
        index=index,
        timestamp_s=index * (1.0 / 30.0),
        source_id="test",
        pointing=Pointing(0.0, 0.0),
    )
    estimate = (
        TargetEstimate(
            pan_deg=0.0,
            tilt_deg=0.0,
            pan_rate=0.0,
            tilt_rate=0.0,
            px=est_px[0],
            py=est_px[1],
            sigma_deg=0.1,
            from_measurement=True,
        )
        if est_px is not None
        else None
    )
    output = PipelineOutput(
        frame_index=index,
        timestamp_s=frame.timestamp_s,
        state=state,
        estimate=estimate,
        detections=(),
        selected=None,
        intent=ControlIntent(mode=ControlIntentMode.TRACK),
        latency_ms=latency_ms,
    )
    cmd = ControlCommand(0.0, 0.0)
    truth = (
        GroundTruthSample(
            frame_index=index,
            timestamp_s=frame.timestamp_s,
            targets=(
                TargetTruth(
                    id="primary",
                    az_deg=0.0,
                    el_deg=0.0,
                    px=truth_px[0],
                    py=truth_px[1],
                    visible=True,
                    in_fov=True,
                ),
            ),
            primary_px=truth_px,
            primary_visible=True,
            boresight_error_px=5.0,
            pointing=Pointing(0.0, 0.0),
        )
        if truth_px is not None
        else None
    )
    return StepResult(frame=frame, output=output, command=cmd, truth=truth)


def test_collector_recording_and_finalize() -> None:
    """Collector records sequence of steps and produces valid RunMetrics."""
    cfg = SkyLockConfig()
    collector = MetricsCollector(cfg)

    for i in range(10):
        step = _make_step(index=i)
        collector.record(step)

    metrics = collector.finalize()
    assert metrics.metrics_version == "1"
    assert metrics.total_frames == 10
    assert metrics.acquisition_time_from_start_s.status == MetricStatus.MEASURED
    assert metrics.tracking_error_px.status == MetricStatus.MEASURED
    assert metrics.pointing_error_px.status == MetricStatus.MEASURED
    assert metrics.centering_error_px.status == MetricStatus.MEASURED
    assert metrics.fps_pipeline.status == MetricStatus.MEASURED


def test_collector_without_ground_truth() -> None:
    """When steps lack ground truth, GT-dependent metrics are NOT_RUN with clear reasons."""
    cfg = SkyLockConfig()
    collector = MetricsCollector(cfg)

    for i in range(5):
        step = _make_step(index=i, truth_px=None)
        collector.record(step)

    metrics = collector.finalize()
    assert metrics.total_frames == 5
    assert metrics.centering_error_px.status == MetricStatus.MEASURED
    assert metrics.fps_pipeline.status == MetricStatus.MEASURED
    assert metrics.tracking_error_px.status == MetricStatus.NOT_RUN
    assert metrics.pointing_error_px.status == MetricStatus.NOT_RUN
    assert metrics.acquisition_time_from_observable_s.status == MetricStatus.NOT_RUN


def test_collector_reset_clears_state() -> None:
    """Calling reset() restores collector to clean slate."""
    cfg = SkyLockConfig()
    collector = MetricsCollector(cfg)

    for i in range(5):
        collector.record(_make_step(index=i))

    assert len(collector._indices) == 5
    collector.reset()
    assert len(collector._indices) == 0

    metrics = collector.finalize()
    assert metrics.total_frames == 0
    assert metrics.acquisition_time_from_start_s.status == MetricStatus.NOT_RUN
