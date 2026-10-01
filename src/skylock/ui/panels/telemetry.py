"""Telemetry display panel presenting real-time tracking metrics and status."""

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

_EM_DASH = "—"


def _format_time(seconds: float | None) -> str:
    """Format duration in seconds as mm:ss.s or em dash if None."""
    if seconds is None:
        return _EM_DASH
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:04.1f}"


class TelemetryPanel(QWidget):
    """Real-time flight and tracking telemetry readout panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(260)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Use a scroll area so many groups fit comfortably
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # 1. State Card
        state_box = QGroupBox("System State")
        state_layout = QVBoxLayout(state_box)
        self.badge = StateBadge()
        state_layout.addWidget(self.badge)
        self.lbl_lock = QLabel("LOCK: UNLOCKED")
        self.lbl_lock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_lock.setStyleSheet(f"font-weight: bold; color: {theme.TEXT_SECONDARY.name()};")
        state_layout.addWidget(self.lbl_lock)
        layout.addWidget(state_box)

        # 2. Source Card
        source_box = QGroupBox("Source")
        s_layout = QFormLayout(source_box)
        self.lbl_source = QLabel(_EM_DASH)
        self.lbl_progress = QLabel(_EM_DASH)
        s_layout.addRow("Input:", self.lbl_source)
        s_layout.addRow("Progress:", self.lbl_progress)
        layout.addWidget(source_box)

        # 3. Detection Card
        det_box = QGroupBox("Detection")
        d_layout = QFormLayout(det_box)
        self.lbl_det_count = QLabel(_EM_DASH)
        self.lbl_best_centroid = QLabel(_EM_DASH)
        self.lbl_est_pos = QLabel(_EM_DASH)
        self.lbl_est_offset = QLabel(_EM_DASH)
        d_layout.addRow("Count:", self.lbl_det_count)
        d_layout.addRow("Best Centroid (px):", self.lbl_best_centroid)
        d_layout.addRow("Est. Position (px):", self.lbl_est_pos)
        d_layout.addRow("Est. Offset (px):", self.lbl_est_offset)
        layout.addWidget(det_box)

        # 4. Gimbal Telemetry Card
        gimbal_box = QGroupBox("Gimbal Telemetry")
        g_layout = QFormLayout(gimbal_box)
        self.lbl_pointing = QLabel("+0.00° / +0.00°")
        self.lbl_mode = QLabel("AUTO")
        self.lbl_cmd_rate = QLabel("+0.00 / +0.00 °/s")
        g_layout.addRow("Pan / Tilt:", self.lbl_pointing)
        g_layout.addRow("Control Mode:", self.lbl_mode)
        g_layout.addRow("Rate Cmd:", self.lbl_cmd_rate)
        layout.addWidget(gimbal_box)

        # 5. Tracking Performance Metrics Card
        metrics_box = QGroupBox("Tracking Metrics")
        m_layout = QFormLayout(metrics_box)

        self.lbl_acq_time = QLabel(_EM_DASH)
        self.lbl_track_err = QLabel(_EM_DASH)
        self.lbl_fps_pipe = QLabel(_EM_DASH)
        self.lbl_fps_wall = QLabel(_EM_DASH)
        self.lbl_latency = QLabel(_EM_DASH)

        self.row_acq_label = QLabel("Acq time (s) [vs truth]:")
        self.row_err_label = QLabel("Track err (px) [vs truth]:")
        m_layout.addRow(self.row_acq_label, self.lbl_acq_time)
        m_layout.addRow(self.row_err_label, self.lbl_track_err)
        m_layout.addRow("Pipeline FPS:", self.lbl_fps_pipe)
        m_layout.addRow("Wall FPS:", self.lbl_fps_wall)
        m_layout.addRow("Latency (ms):", self.lbl_latency)
        layout.addWidget(metrics_box)

        # 6. Run Summary Card
        summary_box = QGroupBox("Run Summary")
        sum_layout = QFormLayout(summary_box)
        self.lbl_lock_retention = QLabel(_EM_DASH)
        self.lbl_loss_events = QLabel(_EM_DASH)
        self.lbl_last_reacq = QLabel(_EM_DASH)
        self.lbl_state_times = QLabel(_EM_DASH)

        sum_layout.addRow("Lock Retention:", self.lbl_lock_retention)
        sum_layout.addRow("Loss Events:", self.lbl_loss_events)
        sum_layout.addRow("Last Reacq (s):", self.lbl_last_reacq)
        sum_layout.addRow("State Time:", self.lbl_state_times)
        layout.addWidget(summary_box)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        self._apply_monospace_styles()

    def _apply_monospace_styles(self) -> None:
        mono_style = "font-family: 'Consolas', 'Courier New', monospace; font-size: 11px;"
        for lbl in (
            self.lbl_source,
            self.lbl_progress,
            self.lbl_det_count,
            self.lbl_best_centroid,
            self.lbl_est_pos,
            self.lbl_est_offset,
            self.lbl_pointing,
            self.lbl_mode,
            self.lbl_cmd_rate,
            self.lbl_acq_time,
            self.lbl_track_err,
            self.lbl_fps_pipe,
            self.lbl_fps_wall,
            self.lbl_latency,
            self.lbl_lock_retention,
            self.lbl_loss_events,
            self.lbl_last_reacq,
            self.lbl_state_times,
        ):
            lbl.setStyleSheet(mono_style)

    def clear(self) -> None:
        """Reset all telemetry to idle state."""
        self.badge.set_state(TrackState.SEARCH)
        self.lbl_lock.setText("LOCK: UNLOCKED")
        self.lbl_lock.setStyleSheet(f"font-weight: bold; color: {theme.TEXT_SECONDARY.name()};")
        self.lbl_source.setText(_EM_DASH)
        self.lbl_progress.setText(_EM_DASH)
        self.lbl_det_count.setText(_EM_DASH)
        self.lbl_best_centroid.setText(_EM_DASH)
        self.lbl_est_pos.setText(_EM_DASH)
        self.lbl_est_offset.setText(_EM_DASH)
        self.lbl_pointing.setText("+0.00° / +0.00°")
        self.lbl_mode.setText("AUTO")
        self.lbl_cmd_rate.setText("+0.00 / +0.00 °/s")
        self.lbl_acq_time.setText(_EM_DASH)
        self.lbl_acq_time.setToolTip("")
        self.lbl_track_err.setText(_EM_DASH)
        self.lbl_track_err.setToolTip("")
        self.lbl_fps_pipe.setText(_EM_DASH)
        self.lbl_fps_wall.setText(_EM_DASH)
        self.lbl_latency.setText(_EM_DASH)
        self.lbl_lock_retention.setText(_EM_DASH)
        self.lbl_loss_events.setText(_EM_DASH)
        self.lbl_last_reacq.setText(_EM_DASH)
        self.lbl_state_times.setText(_EM_DASH)

    def update_telemetry(self, fv: FrameView) -> None:
        """Update all telemetry labels from the incoming FrameView.

        Strict invariant: Any None metric renders as an em dash ('—'), never 0.
        """
        # State & Lock
        self.badge.set_state(fv.track_state)
        if fv.is_locked:
            self.lbl_lock.setText("LOCK: ENGAGED")
            self.lbl_lock.setStyleSheet(f"font-weight: bold; color: {theme.STATUS_SUCCESS.name()};")
        else:
            self.lbl_lock.setText("LOCK: UNLOCKED")
            self.lbl_lock.setStyleSheet(f"font-weight: bold; color: {theme.TEXT_SECONDARY.name()};")

        # Source & Progress
        src_kind = "Simulation" if fv.is_simulation else "MP4"
        self.lbl_source.setText(src_kind)
        if fv.is_simulation:
            self.lbl_progress.setText(f"frame {fv.frame_index}")
        else:
            if fv.total_frames is not None and fv.total_frames > 0:
                self.lbl_progress.setText(f"frame {fv.frame_index + 1} / {fv.total_frames}")
            else:
                self.lbl_progress.setText(f"frame {fv.frame_index + 1}")

        # Detection group
        # count
        self.lbl_det_count.setText(str(fv.n_detections))

        # best centroid
        if fv.best_detection_px is not None:
            self.lbl_best_centroid.setText(
                f"({fv.best_detection_px[0]:.1f}, {fv.best_detection_px[1]:.1f})"
            )
        else:
            self.lbl_best_centroid.setText(_EM_DASH)

        # estimated position
        if fv.estimate is not None:
            self.lbl_est_pos.setText(f"({fv.estimate[0]:.1f}, {fv.estimate[1]:.1f})")
            # est. offset from boresight (dx, dy)
            dx = fv.estimate[0] - fv.boresight_px[0]
            dy = fv.estimate[1] - fv.boresight_px[1]
            self.lbl_est_offset.setText(f"({dx:+.1f}, {dy:+.1f})")
        else:
            self.lbl_est_pos.setText(_EM_DASH)
            self.lbl_est_offset.setText(_EM_DASH)

        # Gimbal
        self.lbl_pointing.setText(f"{fv.pointing_pan_deg:+.2f}° / {fv.pointing_tilt_deg:+.2f}°")
        self.lbl_mode.setText(fv.control_mode)
        self.lbl_cmd_rate.setText(f"{fv.command_pan_rate:+.2f} / {fv.command_tilt_rate:+.2f} °/s")

        # Tracking metrics (Simulation vs MP4 labels and tooltips)
        if fv.is_simulation:
            self.row_acq_label.setText("Acq time (s) [vs truth]:")
            self.row_err_label.setText("Track err (px) [vs truth]:")
            self.lbl_acq_time.setToolTip("")
            self.lbl_track_err.setToolTip("")

            if fv.acquisition_time_s is not None:
                self.lbl_acq_time.setText(f"{fv.acquisition_time_s:.3f}")
            else:
                self.lbl_acq_time.setText(_EM_DASH)

            if fv.tracking_error_px is not None:
                self.lbl_track_err.setText(f"{fv.tracking_error_px:.2f}")
            else:
                self.lbl_track_err.setText(_EM_DASH)
        else:
            # MP4 feed has no ground truth
            self.row_acq_label.setText("Acq time (s):")
            self.row_err_label.setText("Track err (px):")
            self.lbl_acq_time.setText(_EM_DASH)
            self.lbl_acq_time.setToolTip("needs ground truth")
            self.lbl_track_err.setText(_EM_DASH)
            self.lbl_track_err.setToolTip("needs ground truth")

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

        # Run Summary (from fv.live dict)
        live = fv.live if isinstance(fv.live, dict) else {}
        lock_ret = live.get("lock_retention")
        if lock_ret is not None:
            self.lbl_lock_retention.setText(f"{lock_ret * 100.0:.1f}%")
        else:
            self.lbl_lock_retention.setText(_EM_DASH)

        loss_ev = live.get("loss_events")
        if loss_ev is not None:
            self.lbl_loss_events.setText(str(loss_ev))
        else:
            self.lbl_loss_events.setText(_EM_DASH)

        last_reacq = live.get("last_reacq_s")
        if last_reacq is not None:
            self.lbl_last_reacq.setText(f"{last_reacq:.3f}")
        else:
            self.lbl_last_reacq.setText(_EM_DASH)

        state_frames = live.get("state_frames")
        if isinstance(state_frames, dict) and sum(state_frames.values()) > 0:
            # Show summary formatted as S:x A:x T:x L:x R:x (frames or duration)
            # Short codes for readability
            s_cnt = state_frames.get(TrackState.SEARCH.name, 0)
            a_cnt = state_frames.get(TrackState.ACQUIRE.name, 0)
            t_cnt = state_frames.get(TrackState.TRACK.name, 0)
            l_cnt = state_frames.get(TrackState.LOST.name, 0)
            r_cnt = state_frames.get(TrackState.REACQUIRE.name, 0)
            self.lbl_state_times.setText(f"S:{s_cnt} A:{a_cnt} T:{t_cnt} L:{l_cnt} R:{r_cnt}")
            # Tooltip with full breakdown
            breakdown = (
                f"SEARCH: {s_cnt}\nACQUIRE: {a_cnt}\nTRACK: {t_cnt}\n"
                f"LOST: {l_cnt}\nREACQUIRE: {r_cnt}"
            )
            self.lbl_state_times.setToolTip(breakdown)
        else:
            self.lbl_state_times.setText(_EM_DASH)
            self.lbl_state_times.setToolTip("")


__all__ = ("TelemetryPanel",)
