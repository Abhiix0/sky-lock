import { CAMERA_CONFIG } from './config.js';

/**
 * Camera PiP (Picture-in-Picture) panel for the S-1 gimbal camera feed.
 *
 * Renders the offscreen camera feed onto a 2D canvas element with a crosshair
 * overlay and telemetry readout (FOV, pan, tilt).
 */

// ============================================================
// CONFIGURATION
// ============================================================

const PANEL_WIDTH = 320;
const PANEL_HEIGHT = 240;

// ============================================================
// MODULE STATE
// ============================================================

/** @type {HTMLCanvasElement|null} */
let canvas = null;

/** @type {CanvasRenderingContext2D|null} */
let ctx = null;

/** @type {HTMLElement|null} */
let panelEl = null;

/** @type {HTMLElement|null} */
let telemetryEl = null;

/** Reusable ImageData for putImageData (avoids per-frame allocations). */
let imageData = null;

// ============================================================
// PUBLIC API
// ============================================================

/**
 * Initialize the camera PiP panel. Creates and caches DOM references.
 *
 * @param {Object} [callbacks={}] - Optional control callbacks
 * @param {Function} [callbacks.onAimEarth]
 * @param {Function} [callbacks.onAimTarget]
 * @param {Function} [callbacks.onReset]
 * @param {Function} [callbacks.onNudgePan]
 * @param {Function} [callbacks.onNudgeTilt]
 */
export function initCameraPanel(callbacks = {}) {
  panelEl = document.getElementById('gimbal-cam-panel');
  canvas = document.getElementById('gimbal-cam-canvas');
  telemetryEl = document.getElementById('gimbal-cam-telemetry');

  if (!panelEl || !canvas || !telemetryEl) {
    console.warn('⚠️  Gimbal camera panel DOM elements not found');
    return;
  }

  canvas.width = PANEL_WIDTH;
  canvas.height = PANEL_HEIGHT;
  ctx = canvas.getContext('2d', { willReadFrequently: true });

  // Pre-allocate ImageData buffer
  imageData = ctx.createImageData(PANEL_WIDTH, PANEL_HEIGHT);

  // Wire on-screen control buttons
  const btnEarth = document.getElementById('cam-btn-earth');
  if (btnEarth && callbacks.onAimEarth) {
    btnEarth.addEventListener('click', callbacks.onAimEarth);
  }

  const btnTarget = document.getElementById('cam-btn-target');
  if (btnTarget && callbacks.onAimTarget) {
    btnTarget.addEventListener('click', callbacks.onAimTarget);
  }

  const btnReset = document.getElementById('cam-btn-reset');
  if (btnReset && callbacks.onReset) {
    btnReset.addEventListener('click', callbacks.onReset);
  }

  const btnUp = document.getElementById('cam-btn-up');
  if (btnUp && callbacks.onNudgeTilt) {
    btnUp.addEventListener('click', () => callbacks.onNudgeTilt(2));
  }

  const btnDown = document.getElementById('cam-btn-down');
  if (btnDown && callbacks.onNudgeTilt) {
    btnDown.addEventListener('click', () => callbacks.onNudgeTilt(-2));
  }

  const btnLeft = document.getElementById('cam-btn-left');
  if (btnLeft && callbacks.onNudgePan) {
    btnLeft.addEventListener('click', () => callbacks.onNudgePan(-2));
  }

  const btnRight = document.getElementById('cam-btn-right');
  if (btnRight && callbacks.onNudgePan) {
    btnRight.addEventListener('click', () => callbacks.onNudgePan(2));
  }
}

/**
 * Update the camera PiP panel with a new frame and telemetry info.
 *
 * @param {{ width: number, height: number, data: Uint8Array, timestamp: number, frameId: number }} frame
 * @param {{ panDeg: number, tiltDeg: number }} info
 */
export function updateCameraPanel(frame, info) {
  if (!ctx || !panelEl || !canvas) return;

  panelEl.style.display = 'block';

  // ---- Blit frame data (flip Y because readRenderTargetPixels is bottom-up) ----
  if (frame && frame.data && frame.data.length > 0) {
    const src = frame.data;
    const dst = imageData.data;
    const srcW = frame.width;
    const srcH = frame.height;
    const dstW = PANEL_WIDTH;
    const dstH = PANEL_HEIGHT;

    // Scale factor from source to destination
    const scaleX = srcW / dstW;
    const scaleY = srcH / dstH;

    for (let dstY = 0; dstY < dstH; dstY++) {
      // Flip Y: destination row 0 maps to source row (srcH - 1)
      const srcY = Math.min(Math.floor((dstH - 1 - dstY) * scaleY), srcH - 1);
      for (let dstX = 0; dstX < dstW; dstX++) {
        const srcX = Math.min(Math.floor(dstX * scaleX), srcW - 1);
        const srcIdx = (srcY * srcW + srcX) * 4;
        const dstIdx = (dstY * dstW + dstX) * 4;
        dst[dstIdx] = src[srcIdx];
        dst[dstIdx + 1] = src[srcIdx + 1];
        dst[dstIdx + 2] = src[srcIdx + 2];
        dst[dstIdx + 3] = 255;
      }
    }

    ctx.putImageData(imageData, 0, 0);
  }

  // ---- Crosshair overlay at image center ----
  const cx = PANEL_WIDTH / 2;
  const cy = PANEL_HEIGHT / 2;
  const crossSize = 12;

  ctx.strokeStyle = 'rgba(0, 255, 200, 0.8)';
  ctx.lineWidth = 1;

  // Horizontal line
  ctx.beginPath();
  ctx.moveTo(cx - crossSize, cy);
  ctx.lineTo(cx + crossSize, cy);
  ctx.stroke();

  // Vertical line
  ctx.beginPath();
  ctx.moveTo(cx, cy - crossSize);
  ctx.lineTo(cx, cy + crossSize);
  ctx.stroke();

  // Center dot
  ctx.fillStyle = 'rgba(0, 255, 200, 0.9)';
  ctx.beginPath();
  ctx.arc(cx, cy, 2, 0, Math.PI * 2);
  ctx.fill();

  // ---- Telemetry readout ----
  if (telemetryEl && info) {
    const fov = CAMERA_CONFIG.fovDeg.toFixed(1);
    const pan = info.panDeg.toFixed(1);
    const tilt = info.tiltDeg.toFixed(1);
    telemetryEl.textContent = `FOV ${fov}° | PAN ${pan}° | TILT ${tilt}°`;
  }
}

/**
 * Hide the camera PiP panel.
 */
export function hideCameraPanel() {
  if (panelEl) {
    panelEl.style.display = 'none';
  }
}
