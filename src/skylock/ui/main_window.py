"""Primary application window coordinating control panels, video display, and telemetry."""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import QEvent, QMetaObject, QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from skylock.config.models import SkyLockConfig
from skylock.ui.config_editor import ConfigEditor
from skylock.ui.panels.benchmark import BenchmarkPanel
from skylock.ui.panels.controls import ControlsPanel
from skylock.ui.panels.telemetry import TelemetryPanel
from skylock.ui.widgets.camera_view import CameraView
from skylock.ui.widgets.state_timeline import StateTimeline
from skylock.ui.worker import SessionWorker


class ManualSteeringFilter(QObject):
    """Application-level event filter for manual steering with arrow keys and WASD.

    Handles key press/release events globally while respecting focus context:
    - Only active when control mode is MANUAL
    - Ignores auto-repeat events
    - Works even when child widgets (spinboxes, combos) have focus
    - Exception: ignores events when QLineEdit has focus
      and is actively being edited
    - Tracks multiple simultaneous key presses (e.g., Up + Right)
    - Sends (0, 0) rates when window loses focus
    """

    rate_changed = Signal(float, float)  # (pan_rate, tilt_rate)

    def __init__(
        self,
        parent: QObject | None = None,
        manual_rate_deg_s: float = 2.0,
    ) -> None:
        super().__init__(parent)
        self.manual_rate_deg_s = manual_rate_deg_s
        self.is_manual_mode = False
        self._pressed_keys: set[int] = set()

        # Key mappings
        self._pan_keys = {
            Qt.Key.Key_Left: -1.0,
            Qt.Key.Key_Right: 1.0,
            Qt.Key.Key_A: -1.0,
            Qt.Key.Key_D: 1.0,
        }
        self._tilt_keys = {
            Qt.Key.Key_Up: 1.0,
            Qt.Key.Key_Down: -1.0,
            Qt.Key.Key_W: 1.0,
            Qt.Key.Key_S: -1.0,
        }

    def set_manual_mode(self, is_manual: bool) -> None:
        """Update whether manual mode is active."""
        self.is_manual_mode = is_manual
        if not is_manual:
            self._pressed_keys.clear()
            self.rate_changed.emit(0.0, 0.0)

    def set_manual_rate(self, rate_deg_s: float) -> None:
        """Update the manual rate magnitude."""
        self.manual_rate_deg_s = max(0.0, rate_deg_s)
        self._emit_current_rates()

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        """Filter key events for manual steering."""
        if event is None or not self.is_manual_mode:
            return False

        event_type = event.type()

        # Handle window deactivation
        if event_type == QEvent.Type.WindowDeactivate:
            self._pressed_keys.clear()
            self.rate_changed.emit(0.0, 0.0)
            return False

        # Only process key events
        if event_type not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return False

        # Check if focus widget should block steering
        focused = watched if isinstance(watched, QWidget) else QApplication.focusWidget()
        if self._should_ignore_focus(focused):
            return False

        # Ignore auto-repeat
        if event.isAutoRepeat():  # type: ignore[attr-defined]
            return False

        key = event.key()  # type: ignore[attr-defined]
        all_keys = set(self._pan_keys.keys()) | set(self._tilt_keys.keys())

        if key not in all_keys:
            return False

        # Update pressed keys set
        if event_type == QEvent.Type.KeyPress:
            self._pressed_keys.add(key)
        elif event_type == QEvent.Type.KeyRelease:
            self._pressed_keys.discard(key)

        self._emit_current_rates()
        return True  # Consume the event

    def _should_ignore_focus(self, widget: QWidget | None) -> bool:
        """Check if the focused widget should block steering keys."""
        if widget is None:
            return False

        # Block standalone text input, but allow the internal editor used by spinboxes.
        if isinstance(widget, QLineEdit):
            parent = widget.parentWidget()
            while parent is not None:
                if isinstance(parent, QAbstractSpinBox):
                    return False
                parent = parent.parentWidget()
            return True

        # Block for combo boxes with open popups
        return bool(
            isinstance(widget, QComboBox)
            and hasattr(widget, "view")
            and widget.view().isVisible()
        )

    def _emit_current_rates(self) -> None:
        """Calculate and emit rates based on currently pressed keys."""
        pan_rate = 0.0
        tilt_rate = 0.0

        for key in self._pressed_keys:
            if key in self._pan_keys:
                pan_rate += self._pan_keys[key] * self.manual_rate_deg_s
            if key in self._tilt_keys:
                tilt_rate += self._tilt_keys[key] * self.manual_rate_deg_s

        self.rate_changed.emit(pan_rate, tilt_rate)


class MainWindow(QMainWindow):
    """Main application window for the SkyLock tracking interface."""

    def __init__(
        self,
        initial_config: SkyLockConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("SkyLock — Electro-Optical Tracking System")
        self.resize(1280, 800)

        # Single source of truth for configuration
        initial = initial_config if initial_config is not None else SkyLockConfig()
        self.editor = ConfigEditor(initial)
        self.manual_rate_deg_s = 2.0  # Default manual steering rate

        # Initialize worker and thread
        self._worker_thread = QThread(self)
        self._worker = SessionWorker(self.editor.config)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.initialize)

        # Manual steering event filter
        max_slew = self.editor.config.gimbal.slew_rate_deg_s
        self._steering_filter = ManualSteeringFilter(
            self, manual_rate_deg_s=min(self.manual_rate_deg_s, max_slew)
        )
        QApplication.instance().installEventFilter(self._steering_filter)  # type: ignore[union-attr]

        self._build_ui()
        self._connect_signals()

        self._worker_thread.start()

    def _build_ui(self) -> None:
        # Central widget: CameraView with timeline and toolbar
        central_container = QWidget()
        c_layout = QVBoxLayout(central_container)
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(4)

        self.camera_view = CameraView()
        c_layout.addWidget(self.camera_view, stretch=1)

        # State timeline mounted directly under camera view
        self.state_timeline = StateTimeline()
        c_layout.addWidget(self.state_timeline)

        # Bottom toolbar under camera
        bar_layout = QHBoxLayout()
        self.chk_debug_gt = QCheckBox("Show ground truth (debug)")
        self.chk_debug_gt.setChecked(False)
        self.chk_debug_gt.toggled.connect(self._on_toggle_gt)
        bar_layout.addWidget(self.chk_debug_gt)

        self.chk_legend = QCheckBox("Legend")
        self.chk_legend.setChecked(False)
        self.chk_legend.toggled.connect(self._on_toggle_legend)
        bar_layout.addWidget(self.chk_legend)

        bar_layout.addStretch()
        c_layout.addLayout(bar_layout)

        self.setCentralWidget(central_container)

        # Left Dock: Controls
        self.dock_controls = QDockWidget("Controls", self)
        self.controls_panel = ControlsPanel(self.editor)
        self.dock_controls.setWidget(self.controls_panel)
        self.dock_controls.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_controls)

        # Right Dock: Telemetry
        self.dock_telemetry = QDockWidget("Telemetry", self)
        self.telemetry_panel = TelemetryPanel()
        self.dock_telemetry.setWidget(self.telemetry_panel)
        self.dock_telemetry.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_telemetry)

        # Bottom Dock: Benchmark
        self.dock_bench = QDockWidget("Benchmark", self)
        self.bench_panel = BenchmarkPanel()
        self.dock_bench.setWidget(self.bench_panel)
        self.dock_bench.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock_bench)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _connect_signals(self) -> None:
        # Controls -> Worker
        self.controls_panel.start_clicked.connect(self._worker.start_running)
        self.controls_panel.stop_clicked.connect(self._worker.stop_running)
        self.controls_panel.reset_clicked.connect(self._worker.reset_session)
        self.controls_panel.reset_clicked.connect(self._on_reset_ui)
        self.controls_panel.config_changed.connect(self._worker.apply_config)
        self.controls_panel.mode_changed.connect(self._on_mode_changed)

        # Worker -> Views
        self._worker.frame_ready.connect(self.camera_view.update_frame)
        self._worker.frame_ready.connect(self.telemetry_panel.update_telemetry)
        self._worker.frame_ready.connect(self._on_frame_ready)
        self._worker.session_error.connect(self._on_session_error)
        self._worker.running_changed.connect(self._on_running_changed)
        self._worker.session_rebuilt.connect(self._on_session_rebuilt)
        self._worker.session_finished.connect(self._on_session_finished)

        # Manual steering
        self._steering_filter.rate_changed.connect(self._worker.set_manual_rates)

        # Manual rate from controls -> steering filter
        self.controls_panel.spn_manual_rate.valueChanged.connect(
            self._steering_filter.set_manual_rate
        )

        # Back-pressure: camera view acknowledges frames
        self.camera_view.frame_painted.connect(self._worker.ack_frame)

    def _on_frame_ready(self, fv: Any) -> None:  # noqa: ANN401
        """Update timeline with latest state history."""
        if hasattr(fv, "state_history_tail"):
            self.state_timeline.set_history(fv.state_history_tail)

    def _on_mode_changed(self, mode: str) -> None:
        """Handle mode change: update worker and steering filter."""
        self._worker.set_control_mode(mode)
        self._steering_filter.set_manual_mode(mode == "MANUAL")

    def _on_toggle_gt(self, checked: bool) -> None:
        self.camera_view.show_ground_truth = checked

    def _on_toggle_legend(self, checked: bool) -> None:
        self.camera_view.show_legend = checked

    def _on_reset_ui(self) -> None:
        """Clear camera, timeline, and telemetry displays on reset."""
        self.camera_view.clear()
        self.state_timeline.clear()
        self.telemetry_panel.clear()

    def _on_session_error(self, err: str) -> None:
        self.status_bar.showMessage(f"Error: {err}", 5000)

    def _on_running_changed(self, running: bool) -> None:
        state_str = "Running" if running else "Stopped"
        self.status_bar.showMessage(f"Session {state_str}")

    def _on_session_rebuilt(self, msg: str) -> None:
        """Show session rebuilt notification."""
        self.status_bar.showMessage(msg, 3000)

    def _on_session_finished(self, msg: str) -> None:
        """Show persistent end-of-stream message."""
        self.status_bar.showMessage(msg)  # No timeout - persistent

    def closeEvent(self, event: Any) -> None:  # noqa: ANN401
        """Cleanly shut down worker thread on application close."""
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self._steering_filter)

        # Shutdown benchmark panel if it has the method (Phase G5)
        if hasattr(self.bench_panel, "shutdown"):
            self.bench_panel.shutdown()

        # Stop worker using blocking call from worker thread
        QMetaObject.invokeMethod(
            self._worker,
            "shutdown",
            Qt.ConnectionType.BlockingQueuedConnection,
        )

        # Stop and wait for thread
        self._worker_thread.quit()
        if not self._worker_thread.wait(3000):
            # Thread didn't stop in time - log and terminate as last resort
            self.status_bar.showMessage("Warning: Worker thread forced termination")
            self._worker_thread.terminate()
            self._worker_thread.wait(1000)

        event.accept()


def run_app(
    argv: list[str] | None = None,
    initial_config: SkyLockConfig | None = None,
) -> int:
    """Launch the SkyLock graphical user interface."""
    app = QApplication(argv if argv is not None else sys.argv)
    window = MainWindow(initial_config=initial_config)
    window.show()
    return app.exec()


__all__ = ("MainWindow", "run_app")
