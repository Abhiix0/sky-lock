"""Telemetry display panel - compact mission-focused layout (Phase 1 cleanup).

Displays only the essential tracking information:
  - System State (tracking state + lock status)
  - Detection (centroid, estimate)
  - Gimbal pointing (pan/tilt)
  - Performance (acquisition time, tracking error, reacquisition, FPS)

Removed from this panel: raw frame count, wall time, latency, rate command,
duplicate FPS values, loss event counters, state-frame debug breakdown.
The underlying metric calculations in worker.py are unchanged.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from skylock.core.enums import TrackState
from skylock.ui import theme
from skylock.ui.widgets.state_badge import StateBadge
from skylock.ui.worker import FrameView

_EM_DASH = "\u2014"


class TelemetryPanel(QWidget):
    """Compact real-time tracking telemetry readout panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(220)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # 1. System State
        state_box = QGroupBox("System State")
        state_layout = QVBoxLayout(state_box)
        state_layout.setSpacing(4)
        self.badge = StateBadge()
        state_layout.addWidget(self.badge)
        self.lbl_lock = QLabel("LOCK: UNLOCKED")
        self.lbl_lock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_lock.setStyleSheet(
            f"font-weight: bold; color: {theme.TEXT_SECONDARY.name()};")
        state_layout.addWidget(self.lbl_lock)
        layout.addWidget(state_box)

        # 2. Detection
        det_box = QGroupBox("Detection")
        d_layout = QFormLayout(det_box)
        d_layout.setHorizontalSpacing(8)
        self.lbl_det_count = QLabel(_EM_DASH)
        self.lbl_best_centroid = QLabel(_EM_DASH)
        self.lbl_est_pos = QLabel(_EM_DASH)
        d_layout.addRow("Count:", self.lbl_det_count)
        d_layout.addRow("Centroid (px):", self.lbl_best_centroid)
        d_layout.addRow("Estimate (px):", self.lbl_est_pos)
        layout.addWidget(det_box)

        # 3. Gimbal
        gimbal_box = QGroupBox("Gimbal")
        g_layout = QFormLayout(gimbal_box)
        g_layout.setHorizontalSpacing(8)
        self.lbl_pan = QLabel("+0.00°")
        self.lbl_tilt = QLabel("+0.00°")
        g_layout.addRow("Pan:", self.lbl_pan)
        g_layout.addRow("Tilt:", self.lbl_tilt)
        layout.addWidget(gimbal_box)

        # 4. Performance Metrics
        metrics_box = QGroupBox("Performance")
        m_layout = QFormLayout(metrics_box)
        m_layout.setHorizontalSpacing(8)
        self.lbl_acq_time = QLabel(_EM_DASH)
        self.lbl_track_err = QLabel(_EM_DASH)
        self.lbl_last_reacq = QLabel(_EM_DASH)
        self.lbl_fps_pipe = QLabel(_EM_DASH)
        m_layout.addRow("Acquisition (s):", self.lbl_acq_time)
        m_layout.addRow("Track Error (px):", self.lbl_track_err)
        m_layout.addRow("Reacquisition (s):", self.lbl_last_reacq)
        m_layout.addRow("FPS:", self.lbl_fps_pipe)
        layout.addWidget(metrics_box)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        self._apply_monospace_styles()

    def _apply_monospace_styles(self) -> None:
        mono_style = "font-family: \'Consolas\', \'Courier New\', monospace; font-size: 11px;"
        for lbl in (
            self.lbl_det_count,
            self.lbl_best_centroid,
            self.lbl_est_pos,
            self.lbl_pan,
            self.lbl_tilt,
            self.lbl_acq_time,
            self.lbl_track_err,
            self.lbl_last_reacq,
            self.lbl_fps_pipe,
        ):
            lbl.setStyleSheet(mono_style)

    def clear(self) -> None:
        """Reset all telemetry to idle state."""
        self.badge.set_state(TrackState.SEARCH)
        self.lbl_lock.setText("LOCK: UNLOCKED")
        self.lbl_lock.setStyleSheet(
            f"font-weight: bold; color: {theme.TEXT_SECONDARY.name()};")
        self.lbl_det_count.setText(_EM_DASH)
        self.lbl_best_centroid.setText(_EM_DASH)
        self.lbl_est_pos.setText(_EM_DASH)
        self.lbl_pan.setText("+0.00°")
        self.lbl_tilt.setText("+0.00°")
        self.lbl_acq_time.setText(_EM_DASH)
        self.lbl_acq_time.setToolTip("")
        self.lbl_track_err.setText(_EM_DASH)
        self.lbl_track_err.setToolTip("")
        self.lbl_last_reacq.setText(_EM_DASH)
        self.lbl_fps_pipe.setText(_EM_DASH)

    def update_telemetry(self, fv: FrameView) -> None:
        """Update telemetry labels from the incoming FrameView.

        Strict invariant: Any None metric renders as an em dash ('\u2014'), never 0.
        """
        # State & Lock
        self.badge.set_state(fv.track_state)
        if fv.is_locked:
            self.lbl_lock.setText("LOCK: ENGAGED")
            self.lbl_lock.setStyleSheet(
                f"font-weight: bold; color: {theme.STATUS_SUCCESS.name()};")
        else:
            self.lbl_lock.setText("LOCK: UNLOCKED")
            self.lbl_lock.setStyleSheet(
                f"font-weight: bold; color: {theme.TEXT_SECONDARY.name()};")

        # Detection
        self.lbl_det_count.setText(str(fv.n_detections))

        if fv.best_detection_px is not None:
            self.lbl_best_centroid.setText(
                f"({fv.best_detection_px[0]:.1f}, {fv.best_detection_px[1]:.1f})"
            )
        else:
            self.lbl_best_centroid.setText(_EM_DASH)

        if fv.estimate is not None:
            self.lbl_est_pos.setText(f"({fv.estimate[0]:.1f}, {fv.estimate[1]:.1f})")
        else:
            self.lbl_est_pos.setText(_EM_DASH)

        # Gimbal pointing
        self.lbl_pan.setText(f"{fv.pointing_pan_deg:+.2f}°")
        self.lbl_tilt.setText(f"{fv.pointing_tilt_deg:+.2f}°")

        # Performance metrics
        if fv.is_simulation:
            if fv.acquisition_time_s is not None:
                self.lbl_acq_time.setText(f"{fv.acquisition_time_s:.3f}")
                self.lbl_acq_time.setToolTip("")
            else:
                self.lbl_acq_time.setText(_EM_DASH)

            if fv.tracking_error_px is not None:
                self.lbl_track_err.setText(f"{fv.tracking_error_px:.2f}")
                self.lbl_track_err.setToolTip("")
            else:
                self.lbl_track_err.setText(_EM_DASH)
        else:
            # MP4: no ground truth
            self.lbl_acq_time.setText(_EM_DASH)
            self.lbl_acq_time.setToolTip("needs ground truth")
            self.lbl_track_err.setText(_EM_DASH)
            self.lbl_track_err.setToolTip("needs ground truth")

        # Reacquisition time from live metrics
        live = fv.live if isinstance(fv.live, dict) else {}
        last_reacq = live.get("last_reacq_s")
        if last_reacq is not None:
            self.lbl_last_reacq.setText(f"{last_reacq:.3f}")
        else:
            self.lbl_last_reacq.setText(_EM_DASH)

        # FPS (pipeline)
        if fv.fps_pipeline is not None:
            self.lbl_fps_pipe.setText(f"{fv.fps_pipeline:.1f}")
        else:
            self.lbl_fps_pipe.setText(_EM_DASH)


__all__ = ("TelemetryPanel",)
