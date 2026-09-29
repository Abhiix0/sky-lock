import { CAMERA_CONFIG } from './config.js';
import { bodyAnglesToPixel } from './geometry.js';

/**
 * State color palette.
 */
export const STATE_COLORS = {
  SEARCH: '#94a3b8', // Gray
  ACQUIRE: '#f59e0b', // Amber
  TRACK: '#10b981', // Green
  LOST: '#ef4444', // Red
  REACQUIRE: '#f97316' // Orange
};

/**
 * Draw HUD and tracking overlays on top of the PiP camera canvas.
 *
 * @param {CanvasRenderingContext2D} ctx - 2D context of the PiP canvas
 * @param {Object} trackingStatus - Status object from trackingSystem.getStatus()
 * @param {Object} [gimbalState] - Current gimbal telemetry
 * @param {number} [canvasWidth=320]
 * @param {number} [canvasHeight=240]
 */
export function drawOverlay(ctx, trackingStatus, gimbalState, canvasWidth = 320, canvasHeight = 240) {
  if (!ctx || !trackingStatus) return;

  const { state = 'SEARCH', mode = 'AUTO', detection, estimate } = trackingStatus;
  const stateColor = STATE_COLORS[state] || '#94a3b8';

  const scaleX = canvasWidth / CAMERA_CONFIG.width;
  const scaleY = canvasHeight / CAMERA_CONFIG.height;

  ctx.save();

  // 1. Crosshair at optical boresight (center of image)
  const cx = canvasWidth / 2;
  const cy = canvasHeight / 2;
  const crossSize = 10;

  ctx.strokeStyle = 'rgba(0, 255, 200, 0.4)';
  ctx.lineWidth = 1;

  ctx.beginPath();
  ctx.moveTo(cx - crossSize, cy);
  ctx.lineTo(cx + crossSize, cy);
  ctx.moveTo(cx, cy - crossSize);
  ctx.lineTo(cx, cy + crossSize);
  ctx.stroke();

  // Center point
  ctx.fillStyle = 'rgba(0, 255, 200, 0.6)';
  ctx.fillRect(cx - 1, cy - 1, 2, 2);

  // 2. Selected Detection Bounding Box
  if (detection && detection.bbox) {
    const bx0 = detection.bbox.x0 * scaleX;
    const by0 = detection.bbox.y0 * scaleY;
    const bw = (detection.bbox.x1 - detection.bbox.x0 + 1) * scaleX;
    const bh = (detection.bbox.y1 - detection.bbox.y0 + 1) * scaleY;

    ctx.strokeStyle = stateColor;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(bx0 - 2, by0 - 2, bw + 4, bh + 4);

    // Centroid marker
    const dcx = detection.cx * scaleX;
    const dcy = detection.cy * scaleY;
    ctx.fillStyle = stateColor;
    ctx.beginPath();
    ctx.arc(dcx, dcy, 2, 0, Math.PI * 2);
    ctx.fill();
  }

  // 3. Predicted Position Marker and Uncertainty Circle
  if (estimate && gimbalState) {
    const proj = bodyAnglesToPixel(
      estimate.panDeg,
      estimate.tiltDeg,
      gimbalState.panDeg,
      gimbalState.tiltDeg,
      CAMERA_CONFIG
    );

    if (proj.visibleInFront) {
      const predX = proj.px * scaleX;
      const predY = proj.py * scaleY;

      // Small predicted-position diamond
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(predX, predY - 4);
      ctx.lineTo(predX + 4, predY);
      ctx.lineTo(predX, predY + 4);
      ctx.lineTo(predX - 4, predY);
      ctx.closePath();
      ctx.stroke();

      // Sigma circle
      if (estimate.sigmaDeg && estimate.sigmaDeg > 0) {
        // Convert sigma in degrees to pixels on canvas
        const pxPerDeg = (canvasHeight / CAMERA_CONFIG.fovDeg);
        const radiusPx = Math.max(3, Math.min(100, estimate.sigmaDeg * pxPerDeg));

        ctx.strokeStyle = 'rgba(56, 189, 248, 0.35)';
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.arc(predX, predY, radiusPx, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
  }

  // 4. State Badge and Tracking Mode in Top Bar
  ctx.font = '600 10px monospace';
  ctx.textAlign = 'left';

  // State pill
  ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
  ctx.fillRect(8, 8, 80, 18);
  ctx.strokeStyle = stateColor;
  ctx.lineWidth = 1;
  ctx.strokeRect(8, 8, 80, 18);

  ctx.fillStyle = stateColor;
  ctx.fillText(`[${state}]`, 14, 21);

  // Auto / Manual mode indicator
  ctx.fillStyle = mode === 'AUTO' ? '#38bdf8' : '#e2e8f0';
  ctx.textAlign = 'right';
  ctx.fillText(mode, canvasWidth - 10, 20);

  ctx.restore();
}
