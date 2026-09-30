"""Metrics collector recording step results and finalizing consolidated run metrics."""

from __future__ import annotations

import math
import time
from collections.abc import Sequence

from skylock.config.models import SkyLockConfig
from skylock.core.enums import TrackState
from skylock.core.types import Detection, StepResult
from skylock.metrics.calculators import (
    calculate_acquisition_time,
    calculate_centering_error,
    calculate_detection_rates,
    calculate_fps_and_latency,
    calculate_lock_retention,
    calculate_pointing_error,
    calculate_reacquisition,
    calculate_target_loss_rate,
    calculate_tracking_error,
)
from skylock.metrics.status import RunMetrics


class MetricsCollector:
    """Incremental metrics accumulator consuming StepResult stream.

    Maintains the ground-truth firewall: ground-truth is consumed here
    and nowhere else in the tracking, vision, or control subsystems.
    """

    def __init__(self, config: SkyLockConfig) -> None:
        """Initialize MetricsCollector with configuration."""
        self.config = config
        self._boresight_px: tuple[float, float] = (
            config.camera.width / 2.0,
            config.camera.height / 2.0,
        )

        self._t_start_wall: float | None = None
        self._t_end_wall: float | None = None

        # Data buffers
        self._indices: list[int] = []
        self._timestamps_s: list[float] = []
        self._states: list[TrackState] = []
        self._estimates_px: list[tuple[float, float] | None] = []
        self._detections: list[tuple[Detection, ...]] = []
        self._latencies_ms: list[float] = []

        # Ground truth buffers (None if no GT seen)
        self._has_seen_truth: bool = False
        self._gt_px: list[tuple[float, float] | None] = []
        self._gt_visible: list[bool] = []
        self._source_dropped: int = 0

    def reset(self) -> None:
        """Reset all metric accumulation buffers and timers."""
        self._t_start_wall = None
        self._t_end_wall = None
        self._indices.clear()
        self._timestamps_s.clear()
        self._states.clear()
        self._estimates_px.clear()
        self._detections.clear()
        self._latencies_ms.clear()
        self._has_seen_truth = False
        self._gt_px.clear()
        self._gt_visible.clear()
        self._source_dropped = 0

    def record(self, step: StepResult) -> None:
        """Consume a single StepResult from the execution session."""
        now = time.perf_counter()
        if self._t_start_wall is None:
            self._t_start_wall = now
        self._t_end_wall = now

        frame = step.frame
        output = step.output
        truth = step.truth

        self._indices.append(frame.index)
        self._timestamps_s.append(frame.timestamp_s)
        self._states.append(output.state)

        if output.estimate is not None:
            self._estimates_px.append((float(output.estimate.px), float(output.estimate.py)))
        else:
            self._estimates_px.append(None)

        self._detections.append(output.detections)
        self._latencies_ms.append(float(output.latency_ms))

        # Check metadata for dropped frames
        if "dropped_frames" in frame.meta:
            dropped = int(frame.meta["dropped_frames"])
            if dropped > self._source_dropped:
                self._source_dropped = dropped

        # Process ground truth if available
        if truth is not None:
            self._has_seen_truth = True
            if truth.primary_px is not None:
                self._gt_px.append((float(truth.primary_px[0]), float(truth.primary_px[1])))
            else:
                self._gt_px.append(None)
            self._gt_visible.append(truth.primary_visible)
        else:
            if self._has_seen_truth:
                self._gt_px.append(None)
                self._gt_visible.append(False)

    def finalize(self) -> RunMetrics:
        """Calculate consolidated metrics and return RunMetrics object."""
        n_frames = len(self._indices)
        if self._t_start_wall is not None and self._t_end_wall is not None:
            wall_elapsed_s = max(0.0, float(self._t_end_wall - self._t_start_wall))
        else:
            wall_elapsed_s = 0.0

        gt_px_seq: Sequence[tuple[float, float] | None] | None = (
            self._gt_px if self._has_seen_truth else None
        )
        gt_vis_seq: Sequence[bool] | None = (
            self._gt_visible if self._has_seen_truth else None
        )

        # 1. Acquisition time
        acq_from_start, acq_from_obs, acq_success, obs_duration_s = calculate_acquisition_time(
            timestamps_s=self._timestamps_s,
            states=self._states,
            target_visible=gt_vis_seq,
        )

        # 2. Tracking error
        track_err = calculate_tracking_error(
            states=self._states,
            estimates_px=self._estimates_px,
            gt_px=gt_px_seq,
            gt_visible=gt_vis_seq,
        )

        # 3. Pointing error
        point_err = calculate_pointing_error(
            states=self._states,
            gt_px=gt_px_seq,
            gt_visible=gt_vis_seq,
            boresight_px=self._boresight_px,
        )

        # 4. Centering error
        center_err = calculate_centering_error(
            states=self._states,
            estimates_px=self._estimates_px,
            boresight_px=self._boresight_px,
        )

        # 5. Reacquisition
        reacq_metric, reacq_success = calculate_reacquisition(
            timestamps_s=self._timestamps_s,
            states=self._states,
            gt_visible=gt_vis_seq,
            reacquire_timeout_s=self.config.tracking.reacquire_timeout_s,
        )

        # 6. Target loss rate
        loss_rate = calculate_target_loss_rate(states=self._states)

        # 7. Lock retention
        # Use pointing error if GT available, else centering error
        cx, cy = self._boresight_px
        retention_errors: list[float | None] = []
        for k in range(n_frames):
            if self._has_seen_truth and self._gt_visible[k] and self._gt_px[k] is not None:
                gx, gy = self._gt_px[k]  # type: ignore[misc]
                retention_errors.append(float(math.hypot(gx - cx, gy - cy)))
            elif self._estimates_px[k] is not None:
                ex, ey = self._estimates_px[k]  # type: ignore[misc]
                retention_errors.append(float(math.hypot(ex - cx, ey - cy)))
            else:
                retention_errors.append(None)

        lock_retention = calculate_lock_retention(
            states=self._states,
            errors_px=retention_errors,
            lock_radius_px=self.config.requirements.lock_radius_px,
        )

        # 8. Detection rates
        det_rate, det_present_rate = calculate_detection_rates(
            detections_list=self._detections,
            gt_px=gt_px_seq,
            gt_visible=gt_vis_seq,
            association_gate_px=self.config.tracking.association_gate_px,
        )

        # 9. FPS and Latency
        fps_pipe, fps_w, lat_stats, missed = calculate_fps_and_latency(
            latencies_ms=self._latencies_ms,
            wall_elapsed_s=wall_elapsed_s,
            nominal_fps=self.config.camera.fps,
            source_dropped_frames=self._source_dropped,
        )

        return RunMetrics(
            metrics_version="1",
            total_frames=n_frames,
            observable_duration_s=obs_duration_s,
            acquisition_time_from_start_s=acq_from_start,
            acquisition_time_from_observable_s=acq_from_obs,
            successful_acquisition=acq_success,
            tracking_error_px=track_err,
            pointing_error_px=point_err,
            centering_error_px=center_err,
            reacquisition_time_s=reacq_metric,
            successful_reacquisition=reacq_success,
            target_loss_rate=loss_rate,
            lock_retention=lock_retention,
            detection_rate=det_rate,
            detection_present_rate=det_present_rate,
            fps_pipeline=fps_pipe,
            fps_wall=fps_w,
            latency_ms=lat_stats,
            missed_frames=missed,
        )
