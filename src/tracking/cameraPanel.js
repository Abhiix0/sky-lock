import { CAMERA_CONFIG } from './config.js';
import { drawOverlay } from './overlay.js';

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

/** Last rendered frame ID to avoid redundant pixel blits. */
let lastBlitFrameId = -1;

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

  // Wire tracking mode buttons
  const btnAuto = document.getElementById('track-mode-auto');
  const btnManual = document.getElementById('track-mode-manual');
  if (btnAuto && callbacks.onSetTrackingMode) {
    btnAuto.addEventListener('click', () => {
      setTrackingModeUI('AUTO');
      callbacks.onSetTrackingMode('AUTO');
    });
  }
  if (btnManual && callbacks.onSetTrackingMode) {
    btnManual.addEventListener('click', () => {
      setTrackingModeUI('MANUAL');
      callbacks.onSetTrackingMode('MANUAL');
    });
  }
}

/**
 * Update active button style for tracking mode toggle.
 *
 * @param {'AUTO'|'MANUAL'} mode
 */
export function setTrackingModeUI(mode) {
  const btnAuto = document.getElementById('track-mode-auto');
  const btnManual = document.getElementById('track-mode-manual');
  if (btnAuto && btnManual) {
    if (mode === 'AUTO') {
      btnAuto.classList.add('active');
      btnManual.classList.remove('active');
    } else {
      btnAuto.classList.remove('active');
      btnManual.classList.add('active');
    }
  }
}

/**
 * Update the camera PiP panel with a new frame, telemetry info, and tracking overlay.
 *
 * @param {{ width: number, height: number, data: Uint8Array, timestamp: number, frameId: number }} frame
 * @param {{ panDeg: number, tiltDeg: number }} info
 * @param {Object} [trackingStatus] - Telemetry status from trackingSystem.getStatus()
 */
export function updateCameraPanel(frame, info, trackingStatus) {
  if (!ctx || !panelEl || !canvas) return;

  panelEl.style.display = 'block';

  // ---- Blit frame data only when frameId has changed ----
  if (frame && frame.data && frame.data.length > 0 && frame.frameId !== lastBlitFrameId) {
    lastBlitFrameId = frame.frameId;
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

    // Draw rich tracking overlay (bounding box, sigma circle, badges, crosshairs)
    if (trackingStatus) {
      drawOverlay(ctx, trackingStatus, info, PANEL_WIDTH, PANEL_HEIGHT);
    } else {
      // Fallback crosshair
      const cx = PANEL_WIDTH / 2;
      const cy = PANEL_HEIGHT / 2;
      ctx.strokeStyle = 'rgba(0, 255, 200, 0.8)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - 12, cy); ctx.lineTo(cx + 12, cy);
      ctx.moveTo(cx, cy - 12); ctx.lineTo(cx, cy + 12);
      ctx.stroke();
    }
  }

  // ---- Telemetry readout ----
  if (telemetryEl && info) {
    const fov = CAMERA_CONFIG.fovDeg.toFixed(1);
    const pan = info.panDeg.toFixed(1);
    const tilt = info.tiltDeg.toFixed(1);
    const stateStr = trackingStatus ? ` | [${trackingStatus.state}]` : '';
    telemetryEl.textContent = `FOV ${fov}° | PAN ${pan}° | TILT ${tilt}°${stateStr}`;
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
