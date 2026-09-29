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
 * @property {number} maxSlewAccelDegPerSec2 - Maximum slew acceleration in deg/s^2
 * @property {boolean} panWrap     - Whether pan angle wraps across ±180 degrees
 * @property {number} simStepHz     - Fixed simulation timestep frequency in Hz
 * @property {number} maxFeedFramesPerRender - Max feed captures processed per visual render frame
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
  maxSlewRateDegPerSec: 45, // baseline default (peak LOS rate is ~36 deg/s); PS: maxSlewRateDegPerSec = 30
  maxSlewAccelDegPerSec2: 120, // max slew acceleration in deg/s^2
  panWrap: true, // allow pan wrap-around across ±180 deg
  simStepHz: 120, // fixed simulation clock frequency
  maxFeedFramesPerRender: 2, // max feed updates processed per render step
  observerId: 'S-1',
  targetId: 'S-2'
};

/**
 * Slew rate presets (deg/s)
 * Baseline exists because peak line-of-sight rate is ~36 deg/s; PS is 30 deg/s stress preset.
 */
export const SLEW_PRESETS = {
  baseline: 45,
  ps: 30
};
