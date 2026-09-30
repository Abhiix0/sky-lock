"""Telemetry display panel presenting real-time tracking metrics and status."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from skylock.ui.widgets.state_badge import StateBadge
from skylock.ui.worker import FrameView

_EM_DASH = "—"


class TelemetryPanel(QWidget):
    """Real-time flight and tracking telemetry readout panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(240)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 1. State Card
        state_box = QGroupBox("System State")
        state_layout = QVBoxLayout(state_box)
        self.badge = StateBadge()
        state_layout.addWidget(self.badge)
        self.lbl_lock = QLabel("LOCK: UNLOCKED")
        self.lbl_lock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_lock.setStyleSheet("font-weight: bold; color: #9CA3AF;")
        state_layout.addWidget(self.lbl_lock)
        layout.addWidget(state_box)

        # 2. Gimbal Telemetry Card
        gimbal_box = QGroupBox("Gimbal Telemetry")
        g_layout = QFormLayout(gimbal_box)
        self.lbl_pointing = QLabel("+0.00° / +0.00°")
        self.lbl_mode = QLabel("AUTO")
        self.lbl_cmd_rate = QLabel("+0.00 / +0.00 °/s")
        g_layout.addRow("Pan / Tilt:", self.lbl_pointing)
        g_layout.addRow("Control Mode:", self.lbl_mode)
        g_layout.addRow("Rate Cmd:", self.lbl_cmd_rate)
        layout.addWidget(gimbal_box)

        # 3. Tracking Performance Metrics Card
        metrics_box = QGroupBox("Tracking Metrics")
        m_layout = QFormLayout(metrics_box)

        self.lbl_acq_time = QLabel(_EM_DASH)
        self.lbl_track_err = QLabel(_EM_DASH)
        self.lbl_fps_pipe = QLabel(_EM_DASH)
        self.lbl_fps_wall = QLabel(_EM_DASH)
        self.lbl_latency = QLabel(_EM_DASH)

        m_layout.addRow("Acq Time (s):", self.lbl_acq_time)
        m_layout.addRow("Track Err (px):", self.lbl_track_err)
        m_layout.addRow("Pipeline FPS:", self.lbl_fps_pipe)
        m_layout.addRow("Wall FPS:", self.lbl_fps_wall)
        m_layout.addRow("Latency (ms):", self.lbl_latency)
        layout.addWidget(metrics_box)

        # Separator and stretch
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)
        layout.addStretch()

        self._apply_monospace_styles()

    def _apply_monospace_styles(self) -> None:
        mono_style = "font-family: 'Consolas', 'Courier New', monospace; font-size: 12px;"
        for lbl in (
            self.lbl_pointing,
            self.lbl_mode,
            self.lbl_cmd_rate,
            self.lbl_acq_time,
            self.lbl_track_err,
            self.lbl_fps_pipe,
            self.lbl_fps_wall,
            self.lbl_latency,
        ):
            lbl.setStyleSheet(mono_style)

    def clear(self) -> None:
        """Reset all telemetry to idle state."""
        from skylock.core.enums import TrackState
        self.badge.set_state(TrackState.SEARCH)
        self.lbl_lock.setText("LOCK: UNLOCKED")
        self.lbl_lock.setStyleSheet("font-weight: bold; color: #9CA3AF;")
        self.lbl_pointing.setText("+0.00° / +0.00°")
        self.lbl_mode.setText("AUTO")
        self.lbl_cmd_rate.setText("+0.00 / +0.00 °/s")
        self.lbl_acq_time.setText(_EM_DASH)
        self.lbl_track_err.setText(_EM_DASH)
        self.lbl_fps_pipe.setText(_EM_DASH)
        self.lbl_fps_wall.setText(_EM_DASH)
        self.lbl_latency.setText(_EM_DASH)

    def update_telemetry(self, fv: FrameView) -> None:
        """Update all telemetry labels from the incoming FrameView.

        Strict invariant: Any None metric renders as an em dash ('—'), never 0.
        """
        # State & Lock
        self.badge.set_state(fv.track_state)
        if fv.is_locked:
            self.lbl_lock.setText("LOCK: ENGAGED")
            self.lbl_lock.setStyleSheet("font-weight: bold; color: #10B981;")
        else:
            self.lbl_lock.setText("LOCK: UNLOCKED")
            self.lbl_lock.setStyleSheet("font-weight: bold; color: #9CA3AF;")

        # Gimbal
        self.lbl_pointing.setText(f"{fv.pointing_pan_deg:+.2f}° / {fv.pointing_tilt_deg:+.2f}°")
        self.lbl_mode.setText(fv.control_mode)
        self.lbl_cmd_rate.setText(f"{fv.command_pan_rate:+.2f} / {fv.command_tilt_rate:+.2f} °/s")

        # Metrics (honoring None -> em dash)
        if fv.acquisition_time_s is not None:
            self.lbl_acq_time.setText(f"{fv.acquisition_time_s:.3f}")
        else:
            self.lbl_acq_time.setText(_EM_DASH)

        if fv.tracking_error_px is not None:
            self.lbl_track_err.setText(f"{fv.tracking_error_px:.2f}")
        else:
            self.lbl_track_err.setText(_EM_DASH)

        if fv.fps_pipeline is not None:
            self.lbl_fps_pipe.setText(f"{fv.fps_pipeline:.1f}")
        else:
            self.lbl_fps_pipe.setText(_EM_DASH)

        if fv.fps_wall is not None:
            self.lbl_fps_wall.setText(f"{fv.fps_wall:.1f}")
        else:
            self.lbl_fps_wall.setText(_EM_DASH)

        if fv.latency_ms is not None:
            self.lbl_latency.setText(f"{fv.latency_ms:.2f}")
        else:
            self.lbl_latency.setText(_EM_DASH)


__all__ = ("TelemetryPanel",)
