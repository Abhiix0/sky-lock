"""Smoke tests for MainWindow — not xfail, must always pass.

Tests use a bounded processEvents loop instead of QTest.qWait so the worker
thread is not starved under the offscreen platform.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QApplication

from skylock.config.models import SkyLockConfig
from skylock.ui.main_window import MainWindow

pytestmark = pytest.mark.gui

# Maximum wall-clock seconds to wait for async worker state changes.
_TIMEOUT_S = 2.0


def _process_events_for(seconds: float) -> None:
    """Pump Qt event loop for up to `seconds` wall-clock time."""
    app = QApplication.instance()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def test_main_window_constructs_and_closes(qapp) -> None:  # noqa: ANN001
    """MainWindow must be constructable and close cleanly without raising."""
    window = MainWindow(SkyLockConfig())
    window.show()
    qapp.processEvents()

    # Worker thread must be running after construction
    assert window._worker_thread.isRunning(), (
        "Worker thread is not running after MainWindow construction"
    )

    # Process events briefly to let the worker initialise
    _process_events_for(0.3)

    # Close triggers closeEvent which stops the worker and quits the thread
    window.close()
    qapp.processEvents()

    # Give the thread up to _TIMEOUT_S to finish
    deadline = time.monotonic() + _TIMEOUT_S
    while window._worker_thread.isRunning() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert not window._worker_thread.isRunning(), (
        "Worker thread is still running after MainWindow.close()"
    )


def test_camera_view_clear(qapp) -> None:  # noqa: ANN001
    """CameraView.clear() must not raise and must set _frame_view to None."""
    window = MainWindow(SkyLockConfig())
    window.show()
    qapp.processEvents()

    # clear() should work even before any frame is received
    window.camera_view.clear()
    qapp.processEvents()

    assert window.camera_view._frame_view is None, (
        "CameraView._frame_view should be None after clear()"
    )

    window.close()
    # Wait for the thread to finish
    deadline = time.monotonic() + _TIMEOUT_S
    while window._worker_thread.isRunning() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)


def test_controls_panel_present(qapp) -> None:  # noqa: ANN001
    """MainWindow must expose a controls_panel with Start/Stop/Reset buttons."""
    window = MainWindow(SkyLockConfig())
    window.show()
    qapp.processEvents()

    assert hasattr(window, "controls_panel"), "MainWindow has no controls_panel attribute"
    assert hasattr(window.controls_panel, "btn_start")
    assert hasattr(window.controls_panel, "btn_stop")
    assert hasattr(window.controls_panel, "btn_reset")

    window.close()
    deadline = time.monotonic() + _TIMEOUT_S
    while window._worker_thread.isRunning() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
