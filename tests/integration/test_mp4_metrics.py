"""Integration tests for MP4 video metric calculation with and without sidecar."""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np

from skylock.app.session import Session
from skylock.config.models import InputConfig, SkyLockConfig
from skylock.core.enums import MetricStatus
from skylock.input.video import Mp4Source
from skylock.metrics.collector import MetricsCollector


def _create_synthetic_mp4(
    path: Path,
    num_frames: int = 15,
    fps: float = 30.0,
    width: int = 640,
    height: int = 480,
) -> None:
    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height), isColor=False)

    for _ in range(num_frames):
        img = np.zeros((height, width), dtype=np.uint8)
        # Draw bright beacon near center
        cv2.circle(img, (320, 240), 6, 255, -1)
        writer.write(img)

    writer.release()


def test_mp4_run_without_sidecar() -> None:
    """MP4 run without ground-truth sidecar:

    - Ground truth metrics (pointing, tracking, detection-against-gt, acq-from-obs)
      are NOT_RUN with reasons.
    - Centering error, FPS, and acquisition-from-start are MEASURED.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = Path(tmp_dir) / "test_beacon.mp4"
        _create_synthetic_mp4(video_path, num_frames=15, fps=30.0)

        cfg = SkyLockConfig(
            input=InputConfig(kind="mp4", mp4_path=str(video_path)),
        )
        source = Mp4Source(cfg.input)
        source.open()
        try:
            collector = MetricsCollector(cfg)
            session = Session(config=cfg, source=source, collector=collector)
            session.run()

            metrics = collector.finalize()
            assert metrics.total_frames == 15

            # Centering error, FPS, and start acquisition are MEASURED
            assert metrics.centering_error_px.status == MetricStatus.MEASURED
            assert metrics.fps_pipeline.status == MetricStatus.MEASURED
            assert metrics.fps_wall.status == MetricStatus.MEASURED
            assert metrics.acquisition_time_from_start_s.status == MetricStatus.MEASURED

            # Ground-truth dependent metrics are NOT_RUN with explicit reasons
            assert metrics.pointing_error_px.status == MetricStatus.NOT_RUN
            assert "ground truth" in str(metrics.pointing_error_px.reason).lower()

            assert metrics.tracking_error_px.status == MetricStatus.NOT_RUN
            assert "ground truth" in str(metrics.tracking_error_px.reason).lower()

            assert metrics.detection_rate.status == MetricStatus.NOT_RUN
            assert "ground truth" in str(metrics.detection_rate.reason).lower()

            assert metrics.acquisition_time_from_observable_s.status == MetricStatus.NOT_RUN
            assert "ground truth" in str(metrics.acquisition_time_from_observable_s.reason).lower()
        finally:
            source.close()


def test_zero_frame_run_everything_not_run() -> None:
    """A run with zero frames must have all metrics NOT_RUN."""
    cfg = SkyLockConfig()
    collector = MetricsCollector(cfg)

    metrics = collector.finalize()

    assert metrics.total_frames == 0
    assert metrics.acquisition_time_from_start_s.status == MetricStatus.NOT_RUN
    assert metrics.acquisition_time_from_observable_s.status == MetricStatus.NOT_RUN
    assert metrics.tracking_error_px.status == MetricStatus.NOT_RUN
    assert metrics.pointing_error_px.status == MetricStatus.NOT_RUN
    assert metrics.centering_error_px.status == MetricStatus.NOT_RUN
    assert metrics.reacquisition_time_s.status == MetricStatus.NOT_RUN
    assert metrics.target_loss_rate.status == MetricStatus.NOT_RUN
    assert metrics.lock_retention.status == MetricStatus.NOT_RUN
    assert metrics.fps_pipeline.status == MetricStatus.NOT_RUN
    assert metrics.latency_ms.status == MetricStatus.NOT_RUN
    assert metrics.missed_frames.status == MetricStatus.NOT_RUN
