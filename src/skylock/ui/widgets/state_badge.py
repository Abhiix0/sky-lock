"""Modern status badge widget displaying the current tracking state."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QWidget

from skylock.core.enums import TrackState
from skylock.ui import theme

# Distinct high-contrast palette mapping
STATE_COLOR_ITEMS: tuple[tuple[TrackState, QColor], ...] = (
    (TrackState.SEARCH, theme.STATE_SEARCH_PRIMARY),
    (TrackState.ACQUIRE, theme.STATE_ACQUIRE_PRIMARY),
    (TrackState.TRACK, theme.STATE_TRACK_PRIMARY),
    (TrackState.LOST, theme.STATE_LOST_PRIMARY),
    (TrackState.REACQUIRE, theme.STATE_REACQUIRE_PRIMARY),
)


def get_state_color(state: TrackState) -> QColor:
    """Return QColor for a given TrackState."""
    for s, color in STATE_COLOR_ITEMS:
        if s == state:
            return color
    return theme.STATE_DEFAULT_PRIMARY


# For backward compatibility with dict-style lookups without module-level dict assignment
class _StateColorsMapping:
    def get(self, state: TrackState, default: QColor | None = None) -> QColor:
        for s, color in STATE_COLOR_ITEMS:
            if s == state:
                return color
        return default if default is not None else theme.STATE_DEFAULT_PRIMARY

    def __getitem__(self, state: TrackState) -> QColor:
        return self.get(state)


STATE_COLORS = _StateColorsMapping()


def _get_state_style(state: TrackState) -> str:
    """Return styling CSS for a given TrackState."""
    if state == TrackState.SEARCH:
        return f"background-color: {theme.STATE_SEARCH_BG.name()}; color: {theme.STATE_SEARCH_TEXT.name()}; border: 1px solid {theme.STATE_SEARCH_PRIMARY.name()};"
    if state == TrackState.ACQUIRE:
        return f"background-color: {theme.STATE_ACQUIRE_BG.name()}; color: {theme.STATE_ACQUIRE_TEXT.name()}; border: 1px solid {theme.STATE_ACQUIRE_PRIMARY.name()};"
    if state == TrackState.TRACK:
        return f"background-color: {theme.STATE_TRACK_BG.name()}; color: {theme.STATE_TRACK_TEXT.name()}; border: 1px solid {theme.STATE_TRACK_PRIMARY.name()};"
    if state == TrackState.LOST:
        return f"background-color: {theme.STATE_LOST_BG.name()}; color: {theme.STATE_LOST_TEXT.name()}; border: 1px solid {theme.STATE_LOST_PRIMARY.name()};"
    if state == TrackState.REACQUIRE:
        return f"background-color: {theme.STATE_REACQUIRE_BG.name()}; color: {theme.STATE_REACQUIRE_TEXT.name()}; border: 1px solid {theme.STATE_REACQUIRE_PRIMARY.name()};"
    return _DEFAULT_STYLE


_DEFAULT_STYLE = f"background-color: {theme.ALT_BASE_BG.name()}; color: {theme.TEXT_SECONDARY.name()}; border: 1px solid {theme.BORDER_NORMAL.name()};"


class StateBadge(QLabel):
    """Pill badge indicating TrackState with distinct high-contrast colors."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("OFFLINE", parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(28)
        self.setMinimumWidth(100)
        self._apply_style(_DEFAULT_STYLE)

    def set_state(self, state: TrackState | str | None) -> None:
        """Update badge text and color palette based on TrackState."""
        if state is None:
            self.setText("OFFLINE")
            self._apply_style(_DEFAULT_STYLE)
            return

        if isinstance(state, str):
            try:
                state = TrackState(state)
            except ValueError:
                self.setText(state.upper())
                self._apply_style(_DEFAULT_STYLE)
                return

        style = _get_state_style(state)
        self.setText(state.name)
        self._apply_style(style)

    def _apply_style(self, palette_style: str) -> None:
        base = "border-radius: 6px; font-weight: bold;"
        base += " font-size: 12px; padding: 4px 12px;"
        self.setStyleSheet(f"{base} {palette_style}")


__all__ = ("STATE_COLORS", "StateBadge")

