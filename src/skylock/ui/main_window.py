"""Primary application window coordinating control panels, video display, and telemetry."""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import QEvent, QMetaObject, QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import skylock
from skylock.config.models import SkyLockConfig
from skylock.ui import theme
from skylock.ui.config_editor import ConfigEditor
from skylock.ui.panels.benchmark import BenchmarkPanel
from skylock.ui.panels.controls import ControlsPanel
from skylock.ui.panels.telemetry import TelemetryPanel
from skylock.ui.settings import AppSettings
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
        self.setMinimumSize(1100, 700)

        # Settings manager
        self.settings = AppSettings()

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
        self._build_menus()
        self._connect_signals()

        # Restore settings or apply defaults
        restored = self.settings.restore_window_state(self)
        if not restored:
            self.resize(1280, 800)
            self._apply_default_layout()

        # Restore UI flags
        show_gt = self.settings.get_show_ground_truth()
        show_legend = self.settings.get_show_legend()
        self.chk_debug_gt.setChecked(show_gt)
        self.chk_legend.setChecked(show_legend)
        self.camera_view.show_ground_truth = show_gt
        self.camera_view.show_legend = show_legend

        self._worker_thread.start()

    def _build_ui(self) -> None:
        # Central widget: Vertical splitter with camera/timeline top, tabs bottom
        central_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top section: Camera view + state timeline
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(4, 4, 4, 4)
        top_layout.setSpacing(4)

        self.camera_view = CameraView()
        top_layout.addWidget(self.camera_view, stretch=10)

        # State timeline mounted directly under camera view
        self.state_timeline = StateTimeline()
        top_layout.addWidget(self.state_timeline)

        # Bottom toolbar under camera
        bar_layout = QHBoxLayout()
        self.chk_debug_gt = QCheckBox("Show ground truth (debug)")
        self.chk_debug_gt.setChecked(False)
        self.chk_debug_gt.setToolTip("Display ground truth overlay (simulation only)")
        self.chk_debug_gt.toggled.connect(self._on_toggle_gt)
        bar_layout.addWidget(self.chk_debug_gt)

        self.chk_legend = QCheckBox("Legend")
        self.chk_legend.setChecked(False)
        self.chk_legend.setToolTip("Show symbology legend")
        self.chk_legend.toggled.connect(self._on_toggle_legend)
        bar_layout.addWidget(self.chk_legend)

        bar_layout.addStretch()
        top_layout.addLayout(bar_layout)

        central_splitter.addWidget(top_widget)

        # Bottom section: Tabs for Benchmark and other future panels
        self.tab_widget = QTabWidget()
        self.bench_panel = BenchmarkPanel()
        self.tab_widget.addTab(self.bench_panel, "Benchmark")

        central_splitter.addWidget(self.tab_widget)

        # Set splitter stretch factors: camera area gets most space
        central_splitter.setStretchFactor(0, 10)
        central_splitter.setStretchFactor(1, 1)

        # Set default sizes (will be overridden by settings if restored)
        central_splitter.setSizes([600, 220])

        self.central_splitter = central_splitter
        self.setCentralWidget(central_splitter)

        # Left Dock: Controls
        self.dock_controls = QDockWidget("Controls", self)
        self.controls_panel = ControlsPanel(self.editor)
        self.dock_controls.setWidget(self.controls_panel)
        self.dock_controls.setMinimumWidth(340)
        self.dock_controls.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_controls)

        # Right Dock: Telemetry
        self.dock_telemetry = QDockWidget("Telemetry", self)
        self.telemetry_panel = TelemetryPanel()
        self.dock_telemetry.setWidget(self.telemetry_panel)
        self.dock_telemetry.setMinimumWidth(280)
        self.dock_telemetry.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock_telemetry)

        # Status Bar with permanent widgets
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Permanent status widgets
        self.lbl_status_state = QLabel("SEARCH")
        self.lbl_status_state.setToolTip("Current tracking state")
        self.status_bar.addPermanentWidget(self.lbl_status_state)

        self.lbl_status_source = QLabel("simulation")
        self.lbl_status_source.setToolTip("Input source")
        self.status_bar.addPermanentWidget(self.lbl_status_source)

        self.lbl_status_frame = QLabel("frame 0")
        self.lbl_status_frame.setToolTip("Current frame number")
        self.status_bar.addPermanentWidget(self.lbl_status_frame)

        self.lbl_status_fps = QLabel("0.0 fps")
        self.lbl_status_fps.setToolTip("Wall-clock rendering FPS")
        self.status_bar.addPermanentWidget(self.lbl_status_fps)

        self.lbl_status_pending = QLabel("")
        self.status_bar.addPermanentWidget(self.lbl_status_pending)

        self.status_bar.showMessage("Ready")

    def _build_menus(self) -> None:
        """Build menu bar with File, Run, View, and Help menus."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        act_load_config = QAction("&Load Config...", self)
        act_load_config.setToolTip("Load configuration from JSON file")
        act_load_config.triggered.connect(self._on_load_config)
        file_menu.addAction(act_load_config)

        act_save_config = QAction("&Save Config...", self)
        act_save_config.setToolTip("Save current configuration to JSON file")
        act_save_config.triggered.connect(self._on_save_config)
        file_menu.addAction(act_save_config)

        file_menu.addSeparator()

        act_export_json = QAction("Export Benchmark &JSON...", self)
        act_export_json.setToolTip("Export benchmark results as JSON")
        act_export_json.triggered.connect(self.bench_panel._export_json)
        file_menu.addAction(act_export_json)

        act_export_md = QAction("Export Benchmark &Markdown...", self)
        act_export_md.setToolTip("Export benchmark results as Markdown")
        act_export_md.triggered.connect(self.bench_panel._export_md)
        file_menu.addAction(act_export_md)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # Run menu
        run_menu = menubar.addMenu("&Run")

        self.act_start = QAction("&Start", self)
        self.act_start.setShortcut(QKeySequence("Ctrl+R"))
        self.act_start.setToolTip("Start tracking session (Ctrl+R)")
        self.act_start.triggered.connect(self.controls_panel._on_start)
        run_menu.addAction(self.act_start)

        self.act_stop = QAction("S&top", self)
        self.act_stop.setShortcut(QKeySequence("Ctrl+."))
        self.act_stop.setToolTip("Stop tracking session (Ctrl+.)")
        self.act_stop.triggered.connect(lambda: self.controls_panel.stop_clicked.emit())
        run_menu.addAction(self.act_stop)

        self.act_reset = QAction("&Reset", self)
        self.act_reset.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.act_reset.setToolTip("Reset session (Ctrl+Shift+R)")
        self.act_reset.triggered.connect(lambda: self.controls_panel.reset_clicked.emit())
        run_menu.addAction(self.act_reset)

        # View menu
        view_menu = menubar.addMenu("&View")

        act_toggle_controls = self.dock_controls.toggleViewAction()
        act_toggle_controls.setText("&Controls")
        view_menu.addAction(act_toggle_controls)

        act_toggle_telemetry = self.dock_telemetry.toggleViewAction()
        act_toggle_telemetry.setText("&Telemetry")
        view_menu.addAction(act_toggle_telemetry)

        view_menu.addSeparator()

        act_show_gt = QAction("Show &Ground Truth", self, checkable=True)
        act_show_gt.setChecked(self.chk_debug_gt.isChecked())
        act_show_gt.toggled.connect(self.chk_debug_gt.setChecked)
        view_menu.addAction(act_show_gt)

        act_show_legend = QAction("Show &Legend", self, checkable=True)
        act_show_legend.setChecked(self.chk_legend.isChecked())
        act_show_legend.toggled.connect(self.chk_legend.setChecked)
        view_menu.addAction(act_show_legend)

        view_menu.addSeparator()

        act_reset_layout = QAction("Reset &Layout", self)
        act_reset_layout.setToolTip("Reset window layout to defaults")
        act_reset_layout.triggered.connect(self._on_reset_layout)
        view_menu.addAction(act_reset_layout)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        act_about = QAction("&About SkyLock", self)
        act_about.triggered.connect(self._on_about)
        help_menu.addAction(act_about)

        act_shortcuts = QAction("&Keyboard Shortcuts", self)
        act_shortcuts.triggered.connect(self._on_shortcuts)
        help_menu.addAction(act_shortcuts)

    def _apply_default_layout(self) -> None:
        """Apply default window layout (called when settings not restored)."""
        # Default splitter sizes: camera gets ~60% of height
        height = self.height()
        camera_height = int(height * 0.6)
        tabs_height = height - camera_height
        self.central_splitter.setSizes([camera_height, tabs_height])

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

        # Seed link: sync controls panel seed to benchmark panel
        self.controls_panel.spn_seed.valueChanged.connect(
            self.bench_panel.sync_controls_seed
        )
        self.bench_panel.sync_controls_seed(self.controls_panel.spn_seed.value())

        # Back-pressure: camera view acknowledges frames
        self.camera_view.frame_painted.connect(self._worker.ack_frame)

    def _on_frame_ready(self, fv: Any) -> None:  # noqa: ANN401
        """Update timeline and status bar with latest state history."""
        if hasattr(fv, "state_history_tail"):
            self.state_timeline.set_history(fv.state_history_tail)

        # Update status bar permanent widgets
        if hasattr(fv, "track_state"):
            state_name = (
                fv.track_state.name
                if hasattr(fv.track_state, "name")
                else str(fv.track_state)
            )
            self.lbl_status_state.setText(state_name)
        if hasattr(fv, "frame_index"):
            self.lbl_status_frame.setText(f"frame {fv.frame_index}")
        if hasattr(fv, "wall_fps") and fv.wall_fps is not None:
            self.lbl_status_fps.setText(f"{fv.wall_fps:.1f} fps")
        if hasattr(fv, "input_kind"):
            self.lbl_status_source.setText(fv.input_kind)

    def _on_mode_changed(self, mode: str) -> None:
        """Handle mode change: update worker and steering filter."""
        self._worker.set_control_mode(mode)
        self._steering_filter.set_manual_mode(mode == "MANUAL")

    def _on_toggle_gt(self, checked: bool) -> None:
        self.camera_view.show_ground_truth = checked
        self.settings.set_show_ground_truth(checked)

    def _on_toggle_legend(self, checked: bool) -> None:
        self.camera_view.show_legend = checked
        self.settings.set_show_legend(checked)

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

    def _on_load_config(self) -> None:
        """Load configuration from JSON file."""
        last_dir = self.settings.get_last_config_directory()
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Configuration", last_dir or "", "JSON Files (*.json);;All Files (*.*)"
        )
        if path:
            try:
                import json
                from pathlib import Path
                with Path(path).open() as f:
                    data = json.load(f)
                from skylock.config.io import from_dict
                new_config = from_dict(data)
                self.editor.replace_config(new_config)
                self.settings.set_last_config_directory(path)
                self.status_bar.showMessage(f"Loaded config from {Path(path).name}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Load Config Error", f"Failed to load config:\n{e}")

    def _on_save_config(self) -> None:
        """Save current configuration to JSON file."""
        last_dir = self.settings.get_last_config_directory()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Configuration", last_dir or "", "JSON Files (*.json);;All Files (*.*)"
        )
        if path:
            try:
                import json
                from pathlib import Path

                from skylock.config.io import to_dict
                with Path(path).open("w") as f:
                    json.dump(to_dict(self.editor.config), f, indent=2)
                self.settings.set_last_config_directory(path)
                self.status_bar.showMessage(f"Saved config to {Path(path).name}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Save Config Error", f"Failed to save config:\n{e}")

    def _on_reset_layout(self) -> None:
        """Reset window layout to defaults."""
        self.settings.reset_layout()
        QMessageBox.information(
            self,
            "Layout Reset",
            "Window layout will be reset to defaults on next launch."
        )

    def _on_about(self) -> None:
        """Show About dialog."""
        QMessageBox.about(
            self,
            "About SkyLock",
            f"<h3>SkyLock</h3>"
            f"<p>Version {skylock.__version__}</p>"
            f"<p>Electro-Optical Tracking System</p>"
            f"<p>A precision target tracking simulation and control interface.</p>"
        )

    def _on_shortcuts(self) -> None:
        """Show keyboard shortcuts dialog."""
        shortcuts_text = """
        <h3>Keyboard Shortcuts</h3>
        <table cellpadding="4">
        <tr><td><b>Ctrl+R</b></td><td>Start tracking</td></tr>
        <tr><td><b>Ctrl+.</b></td><td>Stop tracking</td></tr>
        <tr><td><b>Ctrl+Shift+R</b></td><td>Reset session</td></tr>
        <tr><td colspan="2">&nbsp;</td></tr>
        <tr><td colspan="2"><b>Manual Control Mode:</b></td></tr>
        <tr><td><b>Arrow Keys</b></td><td>Pan/tilt gimbal</td></tr>
        <tr><td><b>W/A/S/D</b></td><td>Pan/tilt gimbal (alternative)</td></tr>
        <tr><td><b>Up/W</b></td><td>Tilt up</td></tr>
        <tr><td><b>Down/S</b></td><td>Tilt down</td></tr>
        <tr><td><b>Left/A</b></td><td>Pan left</td></tr>
        <tr><td><b>Right/D</b></td><td>Pan right</td></tr>
        </table>
        """
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)

    def closeEvent(self, event: Any) -> None:  # noqa: ANN401
        """Cleanly shut down worker thread and save settings on application close."""
        # Save settings
        self.settings.save_window_state(self)
        self.settings.save_splitter_sizes(self.central_splitter, "main")

        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self._steering_filter)

        # Shutdown benchmark panel
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
    theme.apply_theme(app)
    window = MainWindow(initial_config=initial_config)
    window.show()
    return app.exec()


__all__ = ("MainWindow", "run_app")
