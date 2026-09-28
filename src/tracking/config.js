/**
 * Virtual Camera Configuration for FSOC Tracking System
 *
 * NOTE: These values will be aligned with the official PS parameter table later.
 */

// ============================================================
// CAMERA CONFIGURATION
// ============================================================

/**
 * @typedef {Object} CameraConfig
 * @property {number} fovDeg        - Vertical field of view in degrees
 * @property {number} width         - Render target width in pixels
 * @property {number} height        - Render target height in pixels
 * @property {number} near          - Near clipping plane
 * @property {number} far           - Far clipping plane
 * @property {number} feedRateHz    - Camera feed update rate in Hz
 * @property {number} panLimitDeg   - Maximum pan angle in degrees (±)
 * @property {number} tiltLimitDeg  - Maximum tilt angle in degrees (±)
 * @property {number} maxSlewRateDegPerSec - Maximum slew rate in degrees per second
 * @property {string} observerId    - Satellite ID of the observer (camera host)
 * @property {string} targetId      - Satellite ID of the target
 */

/** @type {CameraConfig} */
export const CAMERA_CONFIG = {
  fovDeg: 20,
  width: 640,
  height: 480,
  near: 0.05,
  far: 1000,
  feedRateHz: 30,
  panLimitDeg: 180,
  tiltLimitDeg: 90,
  maxSlewRateDegPerSec: 30,
  observerId: 'S-1',
  targetId: 'S-2'
};
