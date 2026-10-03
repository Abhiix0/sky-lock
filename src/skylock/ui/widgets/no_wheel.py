"""No-wheel-scroll variants of common Qt input widgets (Rule 7).

Subclasses of QSpinBox/QDoubleSpinBox/QComboBox that intercept wheelEvent and
forward the event to the parent QScrollArea (so the parent panel scrolls),
while leaving the control's value or selection unchanged.
Clicking, typing, keyboard arrows, and slider dragging continue working normally.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QScrollArea,
    QSpinBox,
    QWidget,
)


def _forward_wheel_to_parent_scroll_area(widget: QWidget, event: QEvent) -> None:
    """Forward a wheel event up to the enclosing QScrollArea's viewport."""
    p = widget.parentWidget()
    while p is not None:
        if isinstance(p, QScrollArea):
            QApplication.sendEvent(p.viewport(), event)
            return
        p = p.parentWidget()
    event.ignore()


class NoWheelSpinBox(QSpinBox):
    """QSpinBox that forwards wheel events to parent QScrollArea without changing value."""

    def wheelEvent(self, event: QEvent) -> None:  # type: ignore[override]
        _forward_wheel_to_parent_scroll_area(self, event)


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that forwards wheel events to parent QScrollArea without changing value."""

    def wheelEvent(self, event: QEvent) -> None:  # type: ignore[override]
        _forward_wheel_to_parent_scroll_area(self, event)


class NoWheelComboBox(QComboBox):
    """QComboBox that forwards wheel events to parent QScrollArea without changing selection."""

    def wheelEvent(self, event: QEvent) -> None:  # type: ignore[override]
        _forward_wheel_to_parent_scroll_area(self, event)


__all__ = ("NoWheelComboBox", "NoWheelDoubleSpinBox", "NoWheelSpinBox")
