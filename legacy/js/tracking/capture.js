/**
 * Screen and PiP frame capture utility for Sky Lock.
 *
 * Captures the main 3D constellation view and the gimbal optical camera feed
 * side-by-side into a single high-resolution PNG image, saved via the exporter seam.
 *
 * Inputs: WebGL main canvas, 2D PiP camera canvas, current tracking state, simulation time.
 * Outputs: PNG image file via exporter.saveFile().
 */

import { saveFile } from './exporter.js';

/** Flag indicating a capture has been requested for the next completed render frame. */
let capturePending = false;

/**
 * Request a side-by-side screen capture on the immediate next rendered frame.
 */
export function requestCapture() {
  capturePending = true;
}

/**
 * Query whether a capture is currently pending.
 *
 * @returns {boolean} True if capture requested
 */
export function isCapturePending() {
  return capturePending;
}

/**
 * Cancels any pending capture request.
 */
export function cancelCapture() {
  capturePending = false;
}

/**
 * Capture main canvas and PiP canvas side-by-side immediately post-render.
 *
 * @param {HTMLCanvasElement} mainCanvas - Main Three.js WebGL canvas element
 * @param {HTMLCanvasElement|null} pipCanvas - S-1 gimbal optical camera 2D canvas
 * @param {string} [state='UNKNOWN'] - Current tracking state name (e.g. 'TRACKING')
 * @param {number} [simTime=0] - Current simulation time in seconds
 * @returns {Promise<string|null>} Generated filename if captured, or null
 */
export async function captureFrame(mainCanvas, pipCanvas, state = 'UNKNOWN', simTime = 0) {
  if (!capturePending) return null;
  capturePending = false;

  if (!mainCanvas || typeof document === 'undefined') {
    return null;
  }

  try {
    const mainW = mainCanvas.width || 1600;
    const mainH = mainCanvas.height || 900;

    // Determine PiP dimensions and scale to match main canvas height
    const pipW = pipCanvas && pipCanvas.width > 0 ? pipCanvas.width : 320;
    const pipH = pipCanvas && pipCanvas.height > 0 ? pipCanvas.height : 240;
    const pipScale = mainH / pipH;
    const scaledPipW = Math.round(pipW * pipScale);

    const totalW = mainW + scaledPipW;
    const totalH = mainH;

    const outCanvas = document.createElement('canvas');
    outCanvas.width = totalW;
    outCanvas.height = totalH;
    const ctx = outCanvas.getContext('2d');

    if (!ctx) {
      console.warn('⚠️ Unable to obtain 2D canvas context for frame capture');
      return null;
    }

    // Background fill
    ctx.fillStyle = '#05070d';
    ctx.fillRect(0, 0, totalW, totalH);

    // 1. Draw main 3D constellation view
    ctx.drawImage(mainCanvas, 0, 0, mainW, mainH);

    // 2. Draw PiP gimbal feed (or fallback placeholder if PiP element unavailable)
    if (pipCanvas && pipCanvas.width > 0) {
      ctx.drawImage(pipCanvas, mainW, 0, scaledPipW, totalH);
    } else {
      ctx.fillStyle = '#0a101d';
      ctx.fillRect(mainW, 0, scaledPipW, totalH);
      ctx.fillStyle = '#64748b';
      ctx.font = '24px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('GIMBAL CAM OFFLINE', mainW + scaledPipW / 2, totalH / 2);
    }

    // 3. Subtle vertical cyan divider line between main view and PiP
    ctx.strokeStyle = '#00f0ff';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(mainW, 0);
    ctx.lineTo(mainW, totalH);
    ctx.stroke();

    // 4. State banner overlay on PiP column header
    ctx.fillStyle = 'rgba(5, 7, 13, 0.75)';
    ctx.fillRect(mainW + 10, 10, scaledPipW - 20, 42);
    ctx.strokeStyle = '#00f0ff44';
    ctx.lineWidth = 1;
    ctx.strokeRect(mainW + 10, 10, scaledPipW - 20, 42);

    ctx.fillStyle = '#00f0ff';
    ctx.font = 'bold 16px "SF Mono", Monaco, Consolas, monospace';
    ctx.textAlign = 'left';
    ctx.fillText('S-1 GIMBAL OPTICAL FEED (PiP)', mainW + 24, 36);

    const safeState = String(state || 'UNKNOWN').toLowerCase();
    const safeTime = (typeof simTime === 'number' ? simTime : 0).toFixed(1);
    const filename = `skylock-${safeState}-${safeTime}.png`;

    return new Promise((resolve) => {
      outCanvas.toBlob(async (blob) => {
        if (blob) {
          await saveFile(filename, blob);
          console.log(`📸 Frame capture saved: ${filename} (${totalW}x${totalH})`);
          resolve(filename);
        } else {
          resolve(null);
        }
      }, 'image/png');
    });
  } catch (err) {
    console.error('❌ Failed to capture screenshot frame:', err);
    return null;
  }
}
