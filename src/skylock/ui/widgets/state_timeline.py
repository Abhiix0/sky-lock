"""Timeline widget rendering recent tracking state transitions as colored segments."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from skylock.core.enums import TrackState
from skylock.ui import theme
from skylock.ui.widgets.state_badge import STATE_COLORS

_DEFAULT_SEGMENT_COLOR = theme.BORDER_NORMAL


class StateTimeline(QWidget):
    """Widget ~24px tall painting the recent (t, state) samples as colored segments."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(24)
        self.setMinimumWidth(100)
        self._history: tuple[tuple[float, str], ...] = ()

    def set_history(self, history: tuple[tuple[float, str], ...]) -> None:
        """Update state history tail and trigger repaint."""
        self._history = history
        self.update()

    def clear(self) -> None:
        """Clear timeline samples."""
        self._history = ()
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: ANN401
        """Draw historical state segments horizontally."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        w = float(self.width())
        h = float(self.height())

        # Dark base background
        painter.fillRect(QRectF(0, 0, w, h), theme.WINDOW_BG)

        n = len(self._history)
        if n == 0:
            # Idle placeholder text
            painter.setPen(QPen(theme.TEXT_TERTIARY))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                QRectF(0, 0, w, h),
                Qt.AlignmentFlag.AlignCenter,
                "State Timeline Idle",
            )
            return

        seg_w = w / n
        for i, (_t, state_str) in enumerate(self._history):
            color = _DEFAULT_SEGMENT_COLOR
            try:
                state_enum = TrackState(state_str)
                color = STATE_COLORS.get(state_enum, _DEFAULT_SEGMENT_COLOR)
            except ValueError:
                for s in TrackState:
                    if s.name == state_str:
                        color = STATE_COLORS.get(s, _DEFAULT_SEGMENT_COLOR)
                        break

            x = i * seg_w
            # Ensure at least 1px width for visual continuity
            painter.fillRect(QRectF(x, 1.0, max(1.0, seg_w + 0.5), h - 2.0), color)

        # Thin border
        painter.setPen(QPen(theme.BORDER_NORMAL, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0))


__all__ = ("StateTimeline",)
