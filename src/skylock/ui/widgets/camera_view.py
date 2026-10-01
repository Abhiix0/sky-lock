"""Camera display widget rendering grayscale sensor imagery and tracking overlays."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from skylock.ui.worker import FrameView


class CameraView(QWidget):
    """Custom canvas displaying sensor video with precision tracking symbology."""

    frame_painted = Signal()  # Emitted after paintEvent completes (for back-pressure)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("background-color: #111827;")

        self._frame_view: FrameView | None = None
        self._show_ground_truth: bool = False

    @property
    def show_ground_truth(self) -> bool:
        """Whether debug ground truth target overlays are displayed."""
        return self._show_ground_truth

    @show_ground_truth.setter
    def show_ground_truth(self, value: bool) -> None:
        if self._show_ground_truth != value:
            self._show_ground_truth = value
            self.update()

    def update_frame(self, frame_view: FrameView) -> None:
        """Receive a new FrameView and trigger a widget repaint."""
        self._frame_view = frame_view
        self.update()

    def clear(self) -> None:
        """Clear the camera view back to idle state."""
        self._frame_view = None
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: ANN401
        """Draw sensor frame and HUD overlays."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w_w = self.width()
        w_h = self.height()

        if self._frame_view is None or self._frame_view.image is None:
            painter.fillRect(0, 0, w_w, w_h, QColor("#111827"))
            painter.setPen(QColor("#6B7280"))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(
                QRectF(0, 0, w_w, w_h),
                Qt.AlignmentFlag.AlignCenter,
                "No Video Feed — Click 'Start' to begin",
            )
            return

        fv = self._frame_view
        img_h, img_w = fv.image.shape[:2]

        # Calculate aspect ratio scaling and centering offsets
        scale = min(w_w / img_w, w_h / img_h)
        scaled_w = img_w * scale
        scaled_h = img_h * scale
        ox = (w_w - scaled_w) / 2.0
        oy = (w_h - scaled_h) / 2.0

        # Background letterbox fill
        painter.fillRect(0, 0, w_w, w_h, QColor("#090D16"))

        # Convert numpy uint8 grayscale to QImage
        qimg = QImage(
            fv.image.data,
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
        painter.setPen(QPen(QColor(74, 222, 128, 160), 1, Qt.PenStyle.SolidLine))
        arm = 12.0
        gap = 3.0
        painter.drawLine(QPointF(bx - arm, by), QPointF(bx - gap, by))
        painter.drawLine(QPointF(bx + gap, by), QPointF(bx + arm, by))
        painter.drawLine(QPointF(bx, by - arm), QPointF(bx, by - gap))
        painter.drawLine(QPointF(bx, by + gap), QPointF(bx, by + arm))

        # 2. Detections (yellow centroid rings)
        painter.setPen(QPen(QColor(251, 191, 36, 220), 1.5, Qt.PenStyle.SolidLine))
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
                gate_pen = QPen(QColor(56, 189, 248, 140), 1.0, Qt.PenStyle.DashLine)
                painter.setPen(gate_pen)
                painter.drawRect(gate_rect)

            # Target estimate crosshair (+)
            cross_pen = QPen(QColor(14, 165, 233, 240), 2.0, Qt.PenStyle.SolidLine)
            painter.setPen(cross_pen)
            c_arm = 8.0
            painter.drawLine(QPointF(ex - c_arm, ey), QPointF(ex + c_arm, ey))
            painter.drawLine(QPointF(ex, ey - c_arm), QPointF(ex, ey + c_arm))

        # 4. Ground-truth marker (ONLY if enabled, simulation, and present)
        if self._show_ground_truth and fv.is_simulation and fv.ground_truth_px is not None:
            gx, gy = to_screen(fv.ground_truth_px[0], fv.ground_truth_px[1])
            gt_pen = QPen(QColor(244, 63, 94, 240), 1.5, Qt.PenStyle.SolidLine)
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
            painter.setPen(QColor(244, 63, 94, 220))
            painter.drawText(QPointF(gx + d_size + 2, gy - 2), "GT")

        # Emit signal after painting completes (back-pressure acknowledgment)
        self.frame_painted.emit()


__all__ = ("CameraView",)
