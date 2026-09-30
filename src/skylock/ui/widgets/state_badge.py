"""Modern status badge widget displaying the current tracking state."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from skylock.core.enums import TrackState


def _get_state_style(state: TrackState) -> str:
    """Return styling CSS for a given TrackState."""
    if state == TrackState.SEARCH:
        return "background-color: #1E3A8A; color: #93C5FD; border: 1px solid #3B82F6;"
    if state == TrackState.ACQUIRE:
        return "background-color: #78350F; color: #FDE68A; border: 1px solid #F59E0B;"
    if state == TrackState.TRACK:
        return "background-color: #064E3B; color: #6EE7B7; border: 1px solid #10B981;"
    if state == TrackState.COAST:
        return "background-color: #4C1D95; color: #DDD6FE; border: 1px solid #8B5CF6;"
    if state == TrackState.LOST:
        return "background-color: #881337; color: #FECDD3; border: 1px solid #F43F5E;"
    if state == TrackState.REACQUIRE:
        return "background-color: #7C2D12; color: #FED7AA; border: 1px solid #F97316;"
    return _DEFAULT_STYLE


_DEFAULT_STYLE = (
    "background-color: #1F2937; color: #9CA3AF; border: 1px solid #374151;"
)


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


__all__ = ("StateBadge",)
