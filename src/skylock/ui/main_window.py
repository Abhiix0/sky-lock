"""Primary application window coordinating control panels, video display, and telemetry."""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDockWidget,
    QHBoxLayout,
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
from skylock.ui.worker import SessionWorker


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
        self._manual_pan = 0.0
        self._manual_tilt = 0.0

        # Initialize worker and thread
        self._worker_thread = QThread(self)
        self._worker = SessionWorker(self.editor.config)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.initialize)

        self._build_ui()
        self._connect_signals()

        self._worker_thread.start()

    def _build_ui(self) -> None:
        # Central widget: CameraView with toolbar
        central_container = QWidget()
        c_layout = QVBoxLayout(central_container)
        c_layout.setContentsMargins(4, 4, 4, 4)

        self.camera_view = CameraView()
        c_layout.addWidget(self.camera_view, stretch=1)

        # Bottom toolbar under camera
        bar_layout = QHBoxLayout()
        self.chk_debug_gt = QCheckBox("Show ground truth (debug)")
        self.chk_debug_gt.setChecked(False)
        self.chk_debug_gt.toggled.connect(self._on_toggle_gt)
        bar_layout.addWidget(self.chk_debug_gt)
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

        # Worker -> Views
        self._worker.frame_ready.connect(self.camera_view.update_frame)
        self._worker.frame_ready.connect(self.telemetry_panel.update_telemetry)
        self._worker.session_error.connect(self._on_session_error)
        self._worker.running_changed.connect(self._on_running_changed)

    def _on_toggle_gt(self, checked: bool) -> None:
        self.camera_view.show_ground_truth = checked

    def _on_reset_ui(self) -> None:
        """Clear camera and telemetry displays on reset."""
        self.camera_view.clear()
        self.telemetry_panel.clear()

    def _on_session_error(self, err: str) -> None:
        self.status_bar.showMessage(f"Error: {err}", 5000)

    def _on_running_changed(self, running: bool) -> None:
        state_str = "Running" if running else "Stopped"
        self.status_bar.showMessage(f"Session {state_str}")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle arrow keys for manual gimbal steering in MANUAL mode."""
        step = 2.0  # deg/s
        handled = False
        key = event.key()

        if key == Qt.Key.Key_Left:
            self._manual_pan = -step
            handled = True
        elif key == Qt.Key.Key_Right:
            self._manual_pan = step
            handled = True
        elif key == Qt.Key.Key_Up:
            self._manual_tilt = step
            handled = True
        elif key == Qt.Key.Key_Down:
            self._manual_tilt = -step
            handled = True

        if handled:
            self._worker.set_manual_rates(self._manual_pan, self._manual_tilt)
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Reset rate on key release."""
        key = event.key()
        handled = False
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._manual_pan = 0.0
            handled = True
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self._manual_tilt = 0.0
            handled = True

        if handled:
            self._worker.set_manual_rates(self._manual_pan, self._manual_tilt)
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def closeEvent(self, event: Any) -> None:  # noqa: ANN401
        """Cleanly shut down worker thread on application close."""
        self._worker.stop_running()
        self._worker_thread.quit()
        self._worker_thread.wait(2000)
        event.accept()


def run_app(argv: list[str] | None = None) -> int:
    """Launch the SkyLock graphical user interface."""
    app = QApplication(argv if argv is not None else sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


__all__ = ("MainWindow", "run_app")
