/**
 * Virtual Camera Configuration for FSOC Tracking System
 *
 * NOTE: These values will be aligned with the official PS parameter table later.
 */

export const BEACON_LAYER = 1;

// ============================================================
// BEACON CONFIGURATION
// ============================================================

/**
 * @typedef {Object} BeaconConfig
 * @property {boolean} enabled - Whether beacon is active
 * @property {number} color - Hex color of the beacon halo (saturated magenta: 0xff2bd6)
 * @property {number} coreRadiusPx - Core bright spot radius in pixels
 * @property {number} haloRadiusPx - Halo glow radius in pixels
 * @property {number} brightness - Brightness multiplier
 * @property {number} blinkHz - Blink frequency in Hz (0 = steady)
 * @property {number} blinkDuty - Blink duty cycle [0, 1]
 * @property {boolean} hideTargetBodyInFeed - Hide target satellite mesh in feed
 * @property {boolean} showMarkerInMainView - Show helper ring marker in main view
 */
export const BEACON_CONFIG = {
  enabled: true,
  color: 0xff2bd6,
  coreRadiusPx: 3,
  haloRadiusPx: 12,
  brightness: 1.0,
  blinkHz: 0,
  blinkDuty: 0.5,
  hideTargetBodyInFeed: true,
  showMarkerInMainView: false
};

// ============================================================
// DETECTOR CONFIGURATION
// ============================================================

/**
 * @typedef {Object} DetectorConfig
 * @property {'chroma'|'luma'} mode - Detection mode ('chroma' for magenta beacon, 'luma' fallback)
 * @property {number} lumaThreshold - Intensity threshold for luma mode [0, 255]
 * @property {number} chromaThreshold - Chroma threshold: min(R, B) - G [0, 255]
 * @property {number} minAreaPx - Minimum connected component area in pixels
 * @property {number} maxAreaPx - Maximum connected component area in pixels
 * @property {number} maxBlobs - Maximum number of detected blobs returned
 * @property {number} roiMarginPx - Margin around predicted position for ROI tracking
 */
export const DETECTOR_CONFIG = {
  mode: 'chroma',
  lumaThreshold: 200,
  chromaThreshold: 90,
  minAreaPx: 2,
  maxAreaPx: 900,
  maxBlobs: 8,
  roiMarginPx: 40
};

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
  manualRateDegS: 20, // manual keyboard slew rate in deg/s
  activeSlewPreset: 'baseline', // default slew preset ('baseline' | 'ps')
  observerId: 'S-1',
  targetId: 'S-2'
};

/**
 * Orientation smoothing time constant in seconds.
 * Replaces fixed 0.25 slerp with dt-independent exponential smoothing.
 */
export const SAT_ORIENT_SMOOTH_TAU_SEC = 0.05;

/**
 * Slew rate presets (deg/s)
 * Baseline exists because peak line-of-sight rate is ~36 deg/s; PS is 30 deg/s stress preset.
 */
export const SLEW_PRESETS = {
  baseline: 45,
  ps: 30
};
