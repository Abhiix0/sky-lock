"""Background worker running the Session step loop in a dedicated QThread."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot

from skylock.app.factory import build_session
from skylock.app.session import Session
from skylock.config.models import SkyLockConfig
from skylock.core.enums import ControlMode, InputKind, TrackState
from skylock.core.types import StepResult


@dataclass(frozen=True, slots=True)
class FrameView:
    """Immutable UI presentation DTO emitted after each session step."""

    image: np.ndarray
    frame_index: int
    timestamp_s: float
    track_state: TrackState
    detections: tuple[tuple[float, float, float, float], ...]  # (cx, cy, w, h)
    estimate: tuple[float, float] | None  # (px, py)
    gate_px: float
    boresight_px: tuple[float, float]
    pointing_pan_deg: float
    pointing_tilt_deg: float
    ground_truth_px: tuple[float, float] | None
    is_simulation: bool
    fps_pipeline: float | None
    fps_wall: float | None
    latency_ms: float | None
    acquisition_time_s: float | None
    tracking_error_px: float | None
    is_locked: bool
    control_mode: str
    command_pan_rate: float
    command_tilt_rate: float


class SessionWorker(QObject):
    """QObject executing the tracking Session loop inside a QThread."""

    frame_ready = Signal(object)  # Emits FrameView
    session_error = Signal(str)
    running_changed = Signal(bool)

    def __init__(self, config: SkyLockConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._session: Session | None = None
        self._timer: QTimer | None = None
        self._is_running = False

        # Live metric accumulators
        self._first_track_time_s: float | None = None
        self._first_obs_time_s: float | None = None
        self._frame_counter = 0
        self._wall_start_t: float | None = None
        self._manual_pan_rate = 0.0
        self._manual_tilt_rate = 0.0

    @Slot()
    def initialize(self) -> None:
        """Initialize session and timer within the target thread."""
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._step)
        self._build_new_session(self._config)

    def _build_new_session(self, cfg: SkyLockConfig) -> bool:
        """Rebuild tracking session from a new configuration."""
        try:
            self._session = build_session(cfg)
            self._config = cfg
            # Compute timer interval to achieve target wall FPS
            # Account for processing overhead by using 90% of the ideal period
            # This ensures wall FPS >= camera.fps even with ~10% processing overhead
            target_fps = max(1.0, cfg.camera.fps)
            ideal_period_ms = 1000.0 / target_fps
            timer_interval_ms = max(1, int(ideal_period_ms * 0.9))
            if self._timer is not None:
                self._timer.setInterval(timer_interval_ms)
            self._first_track_time_s = None
            self._first_obs_time_s = None
            self._frame_counter = 0
            self._wall_start_t = None
            return True
        except Exception as e:
            self.session_error.emit(f"Failed to build session: {e}")
            return False

    @Slot()
    def start_running(self) -> None:
        """Start the periodic step timer."""
        if self._is_running:
            return
        if self._session is None and not self._build_new_session(self._config):
            return
        if self._timer is None:
            self.initialize()
        assert self._timer is not None
        self._is_running = True
        self._wall_start_t = time.perf_counter()
        self._frame_counter = 0
        self._timer.start()
        self.running_changed.emit(True)

    @Slot()
    def stop_running(self) -> None:
        """Stop the periodic step timer."""
        if not self._is_running:
            return
        if self._timer is not None:
            self._timer.stop()
        self._is_running = False
        self.running_changed.emit(False)

    @Slot()
    def reset_session(self) -> None:
        """Reset the current session to initial conditions."""
        was_running = self._is_running
        self.stop_running()
        if self._session is not None:
            self._session.reset()
        self._first_track_time_s = None
        self._first_obs_time_s = None
        self._frame_counter = 0
        self._wall_start_t = None
        if was_running:
            self.start_running()

    @Slot(float, float)
    def set_manual_rates(self, pan_rate: float, tilt_rate: float) -> None:
        """Set manual slew rates (deg/s) applied when in MANUAL mode."""
        self._manual_pan_rate = pan_rate
        self._manual_tilt_rate = tilt_rate
        if self._session is not None and hasattr(self._session.controller, "set_manual_rate"):
            self._session.controller.set_manual_rate(pan_rate, tilt_rate)

    @Slot(object)
    def apply_config(self, new_config: SkyLockConfig) -> None:
        """Apply a new SkyLockConfig by rebuilding the session."""
        was_running = self._is_running
        self.stop_running()
        success = self._build_new_session(new_config)
        if success and was_running:
            self.start_running()

    def _step(self) -> None:
        """Execute a single session step and package the FrameView DTO."""
        if self._session is None:
            return

        try:
            res: StepResult | None = self._session.step()
        except Exception as e:
            self.stop_running()
            self.session_error.emit(f"Step failed: {e}")
            return

        if res is None:
            # End of stream reached (e.g. MP4 video ended)
            self.stop_running()
            return

        self._frame_counter += 1
        now = time.perf_counter()
        wall_fps: float | None = None
        if self._wall_start_t is not None and now > self._wall_start_t:
            wall_fps = self._frame_counter / (now - self._wall_start_t)

        frame_view = self._make_frame_view(res, wall_fps)
        self.frame_ready.emit(frame_view)

    def _make_frame_view(self, res: StepResult, wall_fps: float | None) -> FrameView:
        """Convert a StepResult into an immutable UI FrameView."""
        out = res.output
        frame = res.frame
        is_sim = self._config.input.kind in (InputKind.SIMULATION, "simulation")

        # Track first observable and acquisition times
        has_visible_truth = (
            is_sim and res.truth is not None
            and res.truth.primary_visible
        )
        if has_visible_truth and self._first_obs_time_s is None:
            self._first_obs_time_s = frame.timestamp_s

        if out.state == TrackState.TRACK and self._first_track_time_s is None:
            self._first_track_time_s = frame.timestamp_s

        acq_time_s: float | None = None
        if self._first_track_time_s is not None:
            ref_t = self._first_obs_time_s if self._first_obs_time_s is not None else 0.0
            acq_time_s = max(0.0, self._first_track_time_s - ref_t)

        # Tracking error px
        tracking_err: float | None = None
        gt_px: tuple[float, float] | None = None
        has_gt_position = (
            is_sim and res.truth is not None
            and res.truth.primary_visible
            and res.truth.primary_px is not None
        )
        if has_gt_position:
            gt_px = (
                float(res.truth.primary_px[0]),  # type: ignore[index]
                float(res.truth.primary_px[1]),  # type: ignore[index]
            )
            if out.state == TrackState.TRACK and out.estimate is not None:
                dx = out.estimate.px - gt_px[0]
                dy = out.estimate.py - gt_px[1]
                tracking_err = math.hypot(dx, dy)

        # Pipeline FPS
        pipe_fps: float | None = None
        if out.latency_ms > 0:
            pipe_fps = 1000.0 / out.latency_ms

        # Boresight
        bx = self._config.camera.width / 2.0
        by = self._config.camera.height / 2.0

        # Detections
        det_tuples = tuple(
            (float(d.cx), float(d.cy), float(d.bbox[2]), float(d.bbox[3]))
            for d in out.detections
        )

        # Estimate coords
        est_px = (float(out.estimate.px), float(out.estimate.py)) if out.estimate else None

        # Pointing telemetry
        p_pan = frame.pointing.pan_deg if frame.pointing else 0.0
        p_tilt = frame.pointing.tilt_deg if frame.pointing else 0.0

        mode_str = "MANUAL" if self._config.control.mode == ControlMode.MANUAL else "AUTO"

        return FrameView(
            image=np.ascontiguousarray(frame.image.copy()),
            frame_index=frame.index,
            timestamp_s=frame.timestamp_s,
            track_state=out.state,
            detections=det_tuples,
            estimate=est_px,
            gate_px=float(self._config.tracking.association_gate_px),
            boresight_px=(bx, by),
            pointing_pan_deg=p_pan,
            pointing_tilt_deg=p_tilt,
            ground_truth_px=gt_px,
            is_simulation=is_sim,
            fps_pipeline=pipe_fps,
            fps_wall=wall_fps,
            latency_ms=out.latency_ms,
            acquisition_time_s=acq_time_s,
            tracking_error_px=tracking_err,
            is_locked=(out.state == TrackState.TRACK),
            control_mode=mode_str,
            command_pan_rate=float(res.command.pan_rate_deg_s),
            command_tilt_rate=float(res.command.tilt_rate_deg_s),
        )


__all__ = ("FrameView", "SessionWorker")
