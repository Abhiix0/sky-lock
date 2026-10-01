"""Camera display widget rendering grayscale sensor imagery and tracking overlays."""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from skylock.core.enums import TrackState
from skylock.ui import theme
from skylock.ui.worker import FrameView


class CameraView(QWidget):
    """Custom canvas displaying sensor video with precision tracking symbology."""

    frame_painted = Signal()  # Emitted after paintEvent completes (for back-pressure)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setStyleSheet(f"background-color: {theme.WINDOW_BG.name()};")
        self.setMouseTracking(True)

        self._frame_view: FrameView | None = None
        self._image_ref: np.ndarray | None = None
        self._show_ground_truth: bool = False
        self._show_legend: bool = False
        self._mouse_image_pos: tuple[int, int] | None = None

    @property
    def show_ground_truth(self) -> bool:
        """Whether debug ground truth target overlays are displayed."""
        return self._show_ground_truth

    @show_ground_truth.setter
    def show_ground_truth(self, value: bool) -> None:
        if self._show_ground_truth != value:
            self._show_ground_truth = value
            self.update()

    @property
    def show_legend(self) -> bool:
        """Whether symbology overlay legend is displayed."""
        return self._show_legend

    @show_legend.setter
    def show_legend(self, value: bool) -> None:
        if self._show_legend != value:
            self._show_legend = value
            self.update()

    def update_frame(self, frame_view: FrameView) -> None:
        """Receive a new FrameView and trigger a widget repaint."""
        self._frame_view = frame_view
        if frame_view.image is not None:
            self._image_ref = frame_view.image
        self.update()

    def clear(self) -> None:
        """Clear the camera view back to idle state."""
        self._frame_view = None
        self._image_ref = None
        self._mouse_image_pos = None
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Map mouse cursor coordinates to image pixel coordinates."""
        if self._frame_view is None or self._frame_view.image is None:
            self._mouse_image_pos = None
            self.update()
            super().mouseMoveEvent(event)
            return

        w_w = float(self.width())
        w_h = float(self.height())
        img_h, img_w = self._frame_view.image.shape[:2]

        scale = min(w_w / img_w, w_h / img_h)
        scaled_w = img_w * scale
        scaled_h = img_h * scale
        ox = (w_w - scaled_w) / 2.0
        oy = (w_h - scaled_h) / 2.0

        pos = event.position()
        mx, my = pos.x(), pos.y()

        # Check if inside image rect
        if ox <= mx < ox + scaled_w and oy <= my < oy + scaled_h and scale > 0:
            px = int((mx - ox) / scale)
            py = int((my - oy) / scale)
            px = max(0, min(img_w - 1, px))
            py = max(0, min(img_h - 1, py))
            self._mouse_image_pos = (px, py)
        else:
            self._mouse_image_pos = None

        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: Any) -> None:  # noqa: ANN401
        """Clear hover position when mouse leaves widget."""
        self._mouse_image_pos = None
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event: Any) -> None:  # noqa: ANN401
        """Draw sensor frame and HUD overlays."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w_w = self.width()
        w_h = self.height()

        if self._frame_view is None or self._frame_view.image is None:
            painter.fillRect(0, 0, w_w, w_h, theme.WINDOW_BG)
            painter.setPen(theme.TEXT_TERTIARY)
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(
                QRectF(0, 0, w_w, w_h),
                Qt.AlignmentFlag.AlignCenter,
                "No Video Feed — Click 'Start' to begin",
            )
            return

        fv = self._frame_view
        img_h, img_w = fv.image.shape[:2]

        if img_w <= 0 or img_h <= 0 or w_w <= 0 or w_h <= 0:
            return

        # Calculate aspect ratio scaling and centering offsets
        scale = min(w_w / img_w, w_h / img_h)
        scaled_w = img_w * scale
        scaled_h = img_h * scale
        ox = (w_w - scaled_w) / 2.0
        oy = (w_h - scaled_h) / 2.0

        # Background letterbox fill
        painter.fillRect(0, 0, w_w, w_h, theme.DARK_BG)

        # Convert numpy uint8 grayscale to QImage defensively holding reference
        # and explicitly using bytesPerLine = img_w
        self._image_ref = fv.image
        qimg = QImage(
            self._image_ref.data,
            img_w,
            img_h,
            img_w,
            QImage.Format.Format_Grayscale8,
        )
        target_rect = QRectF(ox, oy, scaled_w, scaled_h)
        painter.drawImage(target_rect, qimg)

        # Coordinate transformation helper
        def to_screen(x: float, y: float) -> tuple[float, float]:
            return ox + x * scale, oy + y * scale

        # 1. Boresight crosshair (optical center)
        bx, by = to_screen(fv.boresight_px[0], fv.boresight_px[1])
        painter.setPen(QPen(theme.OVERLAY_BORESIGHT, 1, Qt.PenStyle.SolidLine))
        arm = 12.0
        gap = 3.0
        painter.drawLine(QPointF(bx - arm, by), QPointF(bx - gap, by))
        painter.drawLine(QPointF(bx + gap, by), QPointF(bx + arm, by))
        painter.drawLine(QPointF(bx, by - arm), QPointF(bx, by - gap))
        painter.drawLine(QPointF(bx, by + gap), QPointF(bx, by + arm))

        # 2. Detections (yellow centroid rings)
        painter.setPen(QPen(theme.OVERLAY_DETECTION, 1.5, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for cx, cy, dw, dh in fv.detections:
            scx, scy = to_screen(cx, cy)
            r = max(4.0, (dw + dh) * 0.25 * scale)
            painter.drawEllipse(QPointF(scx, scy), r, r)

        # 3. Association gate box & Target estimate cross
        if fv.estimate is not None:
            ex, ey = to_screen(fv.estimate[0], fv.estimate[1])

            # Gate box
            if fv.gate_px > 0:
                g_size = fv.gate_px * 2.0 * scale
                gate_rect = QRectF(ex - g_size / 2.0, ey - g_size / 2.0, g_size, g_size)
                gate_pen = QPen(theme.OVERLAY_GATE, 1.0, Qt.PenStyle.DashLine)
                painter.setPen(gate_pen)
                painter.drawRect(gate_rect)

            # Target estimate crosshair (+)
            # When state is LOST or REACQUIRE, draw dashed to signal prediction
            is_predicting = fv.track_state in (TrackState.LOST, TrackState.REACQUIRE)
            pen_style = Qt.PenStyle.DashLine if is_predicting else Qt.PenStyle.SolidLine
            cross_color = theme.OVERLAY_ESTIMATE
            cross_pen = QPen(cross_color, 2.0, pen_style)
            painter.setPen(cross_pen)
            c_arm = 8.0
            painter.drawLine(QPointF(ex - c_arm, ey), QPointF(ex + c_arm, ey))
            painter.drawLine(QPointF(ex, ey - c_arm), QPointF(ex, ey + c_arm))

        # 4. Ground-truth marker (ONLY if enabled, simulation, and present)
        if self._show_ground_truth and fv.is_simulation and fv.ground_truth_px is not None:
            gx, gy = to_screen(fv.ground_truth_px[0], fv.ground_truth_px[1])
            gt_pen = QPen(theme.OVERLAY_GT, 1.5, Qt.PenStyle.SolidLine)
            painter.setPen(gt_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            d_size = 6.0
            points = [
                QPointF(gx, gy - d_size),
                QPointF(gx + d_size, gy),
                QPointF(gx, gy + d_size),
                QPointF(gx - d_size, gy),
            ]
            painter.drawPolygon(points)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(theme.OVERLAY_GT_TEXT)
            painter.drawText(QPointF(gx + d_size + 2, gy - 2), "GT")

        # 5. Top-left HUD: Frame index and timestamp
        painter.setFont(QFont("Consolas", 10))
        painter.setPen(theme.OVERLAY_HUD_TEXT)
        hud_text = f"Frame: {fv.frame_index}  |  Time: {fv.timestamp_s:.3f}s"
        painter.drawText(QPointF(10, 20), hud_text)

        # 6. Bottom-right: Mouse hover coordinates (if inside image)
        if self._mouse_image_pos is not None:
            painter.setFont(QFont("Consolas", 10))
            painter.setPen(theme.OVERLAY_COORD_TEXT)
            coord_str = f"X: {self._mouse_image_pos[0]}, Y: {self._mouse_image_pos[1]} px"
            painter.drawText(
                QRectF(w_w - 180, w_h - 25, 170, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                coord_str,
            )

        # 7. Legend overlay (toggled by show_legend)
        if self._show_legend:
            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(theme.OVERLAY_LEGEND_TEXT)
            legend_text = "+ boresight   o detection   [ ] gate   + estimate   ◇ GT"
            painter.drawText(
                QRectF(10, w_h - 25, w_w - 200, 20),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                legend_text,
            )

        # Emit signal after painting completes (back-pressure acknowledgment)
        self.frame_painted.emit()


__all__ = ("CameraView",)
