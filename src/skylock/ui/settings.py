"""Persistent application settings storage and retrieval."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings
from PySide6.QtWidgets import QMainWindow, QSplitter


class AppSettings:
    """Wrapper around QSettings for SkyLock GUI configuration persistence.

    Manages window geometry, dock states, splitter sizes, and user preferences.
    """

    def __init__(self) -> None:
        self._settings = QSettings("SkyLock", "SkyLockGUI")

    def save_window_state(self, window: QMainWindow) -> None:
        """Save window geometry and dock widget state."""
        self._settings.setValue("window/geometry", window.saveGeometry())
        self._settings.setValue("window/state", window.saveState())

    def restore_window_state(self, window: QMainWindow) -> bool:
        """Restore window geometry and dock widget state.

        Returns:
            True if settings were restored, False if defaults should be used.
        """
        geometry = self._settings.value("window/geometry")
        state = self._settings.value("window/state")

        if geometry is not None and isinstance(geometry, QByteArray):
            window.restoreGeometry(geometry)
        else:
            return False

        if state is not None and isinstance(state, QByteArray):
            window.restoreState(state)

        return True

    def save_splitter_sizes(self, splitter: QSplitter, key: str) -> None:
        """Save splitter handle positions."""
        self._settings.setValue(f"splitter/{key}", splitter.saveState())

    def restore_splitter_sizes(self, splitter: QSplitter, key: str) -> bool:
        """Restore splitter handle positions.

        Returns:
            True if restored, False if defaults should be used.
        """
        state = self._settings.value(f"splitter/{key}")
        if state is not None and isinstance(state, QByteArray):
            return splitter.restoreState(state)
        return False

    def get_last_mp4_directory(self) -> str | None:
        """Get the last directory used for MP4 file selection."""
        value = self._settings.value("paths/last_mp4_dir")
        if value is not None and isinstance(value, str):
            path = Path(value)
            if path.exists() and path.is_dir():
                return value
        return None

    def set_last_mp4_directory(self, directory: str) -> None:
        """Save the last directory used for MP4 file selection."""
        path = Path(directory)
        if path.is_file():
            path = path.parent
        self._settings.setValue("paths/last_mp4_dir", str(path))

    def get_last_config_directory(self) -> str | None:
        """Get the last directory used for config file operations."""
        value = self._settings.value("paths/last_config_dir")
        if value is not None and isinstance(value, str):
            path = Path(value)
            if path.exists() and path.is_dir():
                return value
        return None

    def set_last_config_directory(self, directory: str) -> None:
        """Save the last directory used for config file operations."""
        path = Path(directory)
        if path.is_file():
            path = path.parent
        self._settings.setValue("paths/last_config_dir", str(path))

    def get_show_ground_truth(self) -> bool:
        """Get the 'Show ground truth' checkbox state."""
        value = self._settings.value("ui/show_ground_truth", False)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return False

    def set_show_ground_truth(self, show: bool) -> None:
        """Save the 'Show ground truth' checkbox state."""
        self._settings.setValue("ui/show_ground_truth", show)

    def get_show_legend(self) -> bool:
        """Get the 'Show legend' checkbox state."""
        value = self._settings.value("ui/show_legend", False)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() == "true"
        return False

    def set_show_legend(self, show: bool) -> None:
        """Save the 'Show legend' checkbox state."""
        self._settings.setValue("ui/show_legend", show)

    def reset_layout(self) -> None:
        """Clear all window layout and splitter settings, forcing defaults on next launch."""
        self._settings.remove("window/geometry")
        self._settings.remove("window/state")
        self._settings.remove("splitter")

    def clear_all(self) -> None:
        """Clear all settings (for testing or complete reset)."""
        self._settings.clear()


__all__ = ("AppSettings",)
