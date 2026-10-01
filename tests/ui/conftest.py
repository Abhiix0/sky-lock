"""Shared fixtures and configuration for headless GUI tests.

Sets QT_QPA_PLATFORM=offscreen before PySide6 is imported so every test in
tests/ui/ runs without a real display.  The module is skipped automatically
on environments where PySide6 is not installed (it is an optional extra).
"""

from __future__ import annotations

import os
import sys

# Must be set before QApplication is created.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Skip the entire module if PySide6 is absent.
pytest = __import__("pytest")
pytest.importorskip("PySide6")

import pytest  # noqa: E402  (re-import with full binding after importorskip guard)
from PySide6.QtWidgets import QApplication  # noqa: E402

from skylock.config.models import SkyLockConfig  # noqa: E402
from skylock.ui.panels.controls import ControlsPanel  # noqa: E402

# All tests in tests/ui/ carry the gui marker automatically.
pytestmark = pytest.mark.gui


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication instance (reused across all tests in the session)."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    yield app
    # Do NOT call app.quit() here — other session-scoped fixtures may still need it.


@pytest.fixture()
def controls(qapp):  # noqa: ANN001
    """Fresh ControlsPanel backed by a default SkyLockConfig, shown offscreen."""
    panel = ControlsPanel(SkyLockConfig())
    panel.show()
    yield panel
    panel.close()
