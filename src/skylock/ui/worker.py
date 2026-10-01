"""Background worker running the Session step loop in a dedicated QThread."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QMetaObject, QObject, QTimer, Qt, Signal, Slot

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
    dropped_ui_frames: int


class SessionWorker(QObject):
    """QObject executing the tracking Session loop inside a QThread."""

    frame_ready = Signal(object)  # Emits FrameView
    session_error = Signal(str)
    running_changed = Signal(bool)
    session_rebuilt = Signal(str)  # Emitted after successful config rebuild
    session_finished = Signal(str)  # Emitted when stream ends

    def __init__(
        self,
        config: SkyLockConfig,
        parent: QObject | None = None,
        speed: float = 1.0,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._session: Session | None = None
        self._timer: QTimer | None = None
        self._is_running = False
        self._shutdown_requested = False
        self.speed = max(0.0, speed)  # Speed multiplier (>0), 0 => interval 0

        # Timing: single-shot timer with deadline tracking
        self._next_deadline: float = 0.0
        self._period_s: float = 1.0 / 30.0  # Will be set from config

        # Live metric accumulators
        self._first_track_time_s: float | None = None
        self._first_obs_time_s: float | None = None
        self._frame_counter = 0
        self._wall_frame_times: deque[float] = deque(maxlen=60)  # 2s window at 30fps
        self._latency_samples: deque[float] = deque(maxlen=30)

        # Manual control state (survives rebuilds)
        self._manual_pan_rate = 0.0
        self._manual_tilt_rate = 0.0
        self._mode_str = "AUTO"  # Current mode

        # Back-pressure
        self._pending_frames = 0
        self._dropped_ui_frames = 0

    @Slot()
    def initialize(self) -> None:
        """Initialize session and timer within the target thread."""
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._step)
        self._build_new_session(self._config)

    @Slot()
    def shutdown(self) -> None:
        """Safely shut down the worker from within its thread."""
        self._shutdown_requested = True
        if self._timer is not None:
            self._timer.stop()
        self._is_running = False

    def _build_new_session(self, cfg: SkyLockConfig) -> bool:
        """Rebuild tracking session from a new configuration."""
        try:
            self._session = build_session(cfg)
            self._config = cfg

            # Compute period for real-time pacing (no 0.9 factor)
            target_fps = max(1.0, cfg.camera.fps)
            self._period_s = 1.0 / target_fps

            # Reset timing and metrics
            self._next_deadline = 0.0
            self._first_track_time_s = None
            self._first_obs_time_s = None
            self._frame_counter = 0
            self._wall_frame_times.clear()
            self._latency_samples.clear()
            self._dropped_ui_frames = 0
            self._pending_frames = 0

            # Restore control mode and manual rates
            if self._session is not None:
                self._apply_control_state()

            return True
        except Exception as e:
            self.session_error.emit(f"Failed to build session: {e}")
            return False

    def _apply_control_state(self) -> None:
        """Apply stored control mode and manual rates to the session."""
        if self._session is None:
            return

        # Set control mode
        if hasattr(self._session.controller, "set_mode"):
            mode_enum = ControlMode.MANUAL if self._mode_str == "MANUAL" else ControlMode.AUTO
            self._session.controller.set_mode(mode_enum)

        # Set manual rates
        if hasattr(self._session.controller, "set_manual_rate"):
            self._session.controller.set_manual_rate(
                self._manual_pan_rate, self._manual_tilt_rate
            )

    @Slot()
    def start_running(self) -> None:
        """Start the single-shot step timer with deadline-based pacing."""
        if self._is_running or self._shutdown_requested:
            return
        if self._session is None and not self._build_new_session(self._config):
            return
        if self._timer is None:
            self.initialize()
        assert self._timer is not None

        self._is_running = True
        self._next_deadline = time.perf_counter()
        self._frame_counter = 0
        self._wall_frame_times.clear()
        self._timer.start(0)  # Trigger first step immediately
        self.running_changed.emit(True)

    @Slot()
    def stop_running(self) -> None:
        """Stop the single-shot step timer."""
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
        self._wall_frame_times.clear()
        self._latency_samples.clear()
        self._dropped_ui_frames = 0
        self._pending_frames = 0
        self._next_deadline = 0.0
        if was_running:
            self.start_running()

    @Slot(str)
    def set_control_mode(self, mode: str) -> None:
        """Change control mode without rebuilding the session."""
        self._mode_str = mode
        if self._session is None:
            return

        if hasattr(self._session.controller, "set_mode"):
            mode_enum = ControlMode.MANUAL if mode == "MANUAL" else ControlMode.AUTO
            self._session.controller.set_mode(mode_enum)

    @Slot(float, float)
    def set_manual_rates(self, pan_rate: float, tilt_rate: float) -> None:
        """Set manual slew rates (deg/s) applied when in MANUAL mode."""
        self._manual_pan_rate = pan_rate
        self._manual_tilt_rate = tilt_rate
        if self._session is not None and hasattr(self._session.controller, "set_manual_rate"):
            self._session.controller.set_manual_rate(pan_rate, tilt_rate)

    @Slot()
    def ack_frame(self) -> None:
        """Acknowledge that the UI has finished processing a frame."""
        if self._pending_frames > 0:
            self._pending_frames -= 1

    @Slot(object)
    def apply_config(self, new_config: SkyLockConfig) -> None:
        """Apply a new SkyLockConfig by rebuilding the session."""
        was_running = self._is_running
        self.stop_running()
        success = self._build_new_session(new_config)
        if success:
            self.session_rebuilt.emit("Configuration applied")
            if was_running:
                self.start_running()

    def _step(self) -> None:
        """Execute a single session step with deadline-based pacing."""
        if self._session is None or self._shutdown_requested:
            return

        try:
            res: StepResult | None = self._session.step()
        except Exception as e:
            self.stop_running()
            self.session_error.emit(f"Step failed: {e}")
            return

        if res is None:
            # End of stream reached
            self.stop_running()
            is_mp4 = self._config.input.kind in (InputKind.MP4, "mp4")
            msg = (
                f"End of stream after {self._frame_counter} frames"
                if is_mp4
                else "Run finished"
            )
            self.session_finished.emit(msg)
            return

        self._frame_counter += 1
        now = time.perf_counter()

        # Update wall FPS window
        self._wall_frame_times.append(now)

        # Update latency samples for smoothing
        if res.output.latency_ms > 0:
            self._latency_samples.append(res.output.latency_ms)

        # Check back-pressure: skip emitting if UI is behind
        skip_emit = self._pending_frames >= 2
        if skip_emit:
            self._dropped_ui_frames += 1
        else:
            frame_view = self._make_frame_view(res)
            self._pending_frames += 1
            self.frame_ready.emit(frame_view)

        # Schedule next step with deadline-based pacing
        if self._is_running and not self._shutdown_requested:
            self._next_deadline += self._period_s / max(0.001, self.speed)
            delay_s = max(0.0, self._next_deadline - time.perf_counter())
            delay_ms = int(delay_s * 1000) if self.speed > 0 else 0
            if self._timer is not None:
                self._timer.start(delay_ms)

    def _make_frame_view(self, res: StepResult) -> FrameView:
        """Convert a StepResult into an immutable UI FrameView."""
        out = res.output
        frame = res.frame
        is_sim = self._config.input.kind in (InputKind.SIMULATION, "simulation")

        # Track first observable and acquisition times
        has_visible_truth = (
            is_sim and res.truth is not None and res.truth.primary_visible
        )
        if has_visible_truth and self._first_obs_time_s is None:
            self._first_obs_time_s = frame.timestamp_s

        if out.state == TrackState.TRACK and self._first_track_time_s is None:
            self._first_track_time_s = frame.timestamp_s

        acq_time_s: float | None = None
        if self._first_track_time_s is not None:
            ref_t = (
                self._first_obs_time_s if self._first_obs_time_s is not None else 0.0
            )
            acq_time_s = max(0.0, self._first_track_time_s - ref_t)

        # Tracking error px
        tracking_err: float | None = None
        gt_px: tuple[float, float] | None = None
        has_gt_position = (
            is_sim
            and res.truth is not None
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

        # Smoothed pipeline FPS from latency samples
        pipe_fps: float | None = None
        if len(self._latency_samples) > 0:
            mean_latency = sum(self._latency_samples) / len(self._latency_samples)
            if mean_latency > 0:
                pipe_fps = 1000.0 / mean_latency

        # Wall FPS from 2.0s window (minimum 5 frames)
        wall_fps: float | None = None
        if len(self._wall_frame_times) >= 5:
            window_duration = self._wall_frame_times[-1] - self._wall_frame_times[0]
            if window_duration > 0:
                wall_fps = (len(self._wall_frame_times) - 1) / window_duration

        # Boresight
        bx = self._config.camera.width / 2.0
        by = self._config.camera.height / 2.0

        # Detections
        det_tuples = tuple(
            (float(d.cx), float(d.cy), float(d.bbox[2]), float(d.bbox[3]))
            for d in out.detections
        )

        # Estimate coords
        est_px = (
            (float(out.estimate.px), float(out.estimate.py)) if out.estimate else None
        )

        # Pointing telemetry
        p_pan = frame.pointing.pan_deg if frame.pointing else 0.0
        p_tilt = frame.pointing.tilt_deg if frame.pointing else 0.0

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
            control_mode=self._mode_str,
            command_pan_rate=float(res.command.pan_rate_deg_s),
            command_tilt_rate=float(res.command.tilt_rate_deg_s),
            dropped_ui_frames=self._dropped_ui_frames,
        )


__all__ = ("FrameView", "SessionWorker")
