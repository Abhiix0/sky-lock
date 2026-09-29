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
// BEACON CODING & IDENTIFICATION CONFIGURATION (Phase 3B)
// ============================================================

export const BEACON_CODE = {
  bits: '10110010',
  bitPeriodSec: 0.1, // 100 ms per bit = 3 feed frames at 30 Hz
  samplesPerBit: 3,
  mode: 'steady' // 'steady' | 'code' (steady by default per 3B requirements)
};

export const ID_CONFIG = {
  idThreshold: 0.70, // Matched filter score threshold for confirmation
  idConfirmFrames: 3, // Consecutive frames above threshold to confirm ID
  historyWindowFrames: 48, // N = 2 * code length in frames (2 * 8 * 3 = 48)
  gateInitialPx: 35,
  gateGrowthPxPerFrame: 3,
  gateMaxPx: 90,
  maxMissFrames: 6,
  intensityThreshold: 40
};

// ============================================================
// DECOY CONFIGURATION (Phase 3B)
// ============================================================

export const DECOY_CONFIG = {
  enabled: false,
  count: 3, // Number of active decoys when enabled
  starCount: 2,
  decoySatCount: 1,
  glintCount: 1,
  glintRateHz: 1.5,
  seed: 42
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
// KALMAN TRACKER CONFIGURATION
// ============================================================

/**
 * @typedef {Object} KalmanConfig
 * @property {number} qAccelDegS2 - Continuous process noise acceleration variance (deg/s^2)^2
 * @property {number} rMeasDeg - Measurement noise standard deviation in degrees
 * @property {number} gateThresholdSigma - Innovation gating threshold in sigmas
 */
export const KALMAN_CONFIG = {
  qAccelDegS2: 25.0,
  rMeasDeg: 0.1,
  gateThresholdSigma: 4.0
};

// ============================================================
// CONTROLLER CONFIGURATION
// ============================================================

/**
 * @typedef {Object} ControllerConfig
 * @property {number} kp - Proportional gain
 * @property {number} ki - Integral gain
 * @property {number} kd - Derivative gain
 * @property {number} kff - Feed-forward velocity gain
 * @property {number} dFilterAlpha - Low-pass filter smoothing for derivative term [0, 1]
 * @property {number} integralClampDegS - Anti-windup clamp on integral accumulation
 */
export const CONTROLLER_CONFIG = {
  kp: 4.0,
  ki: 0.5,
  kd: 0.2,
  kff: 1.0,
  dFilterAlpha: 0.2,
  integralClampDegS: 8.0
};

// ============================================================
// TRACKING STATE MACHINE & SCAN CONFIGURATION
// ============================================================

/**
 * @typedef {Object} TrackingConfig
 * @property {number} overlap - Overlap fraction between adjacent scan FOVs [0, 1]
 * @property {number} tiltScanLimitDeg - Elevation coverage limit in degrees (±)
 * @property {number} scanRateDegS - Scanning slew rate in deg/s
 * @property {number} reacquireMaxRadiusDeg - Maximum search radius for spiral reacquisition
 * @property {number} minSnrSearch - Minimum SNR threshold to trigger acquisition from search
 * @property {number} acquireConfirmFrames - Consecutive confirmed detections to enter track
 * @property {number} acquireTimeoutSec - Timeout in seconds before aborting unconfirmed acquire
 * @property {number} lostMissFrames - Consecutive missed frames before entering coasting
 * @property {number} coastMaxSec - Maximum duration to coast on prediction before reacquire
 */
export const TRACKING_CONFIG = {
  overlap: 0.2,
  tiltScanLimitDeg: 55,
  scanRateDegS: 35,
  reacquireMaxRadiusDeg: 45,
  minSnrSearch: 3.0,
  acquireConfirmFrames: 3,
  acquireTimeoutSec: 1.0,
  lostMissFrames: 5,
  coastMaxSec: 10.0
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

// ============================================================
// DISTURBANCE PRESETS & CONFIGURATION
// ============================================================

/**
 * Disturbance presets: Off / Low / Med / High.
 * Med challenges but maintains lock (>= 80% visible time).
 * High degrades and recovers via REACQUIRE.
 */
export const DISTURBANCE_PRESETS = {
  OFF: {
    name: 'Off',
    wanderRmsPx: 0,
    wanderCornerHz: 2.0,
    scintillationSigma: 0,
    jitterRmsDeg: 0,
    vibrationHz: 10.0,
    noiseSigma: 0,
    hotPixelsCount: 0,
    blurRadiusPx: 0,
    dropProbability: 0
  },
  LOW: {
    name: 'Low',
    wanderRmsPx: 1.0,
    wanderCornerHz: 2.0,
    scintillationSigma: 0.15,
    jitterRmsDeg: 0.04,
    vibrationHz: 10.0,
    noiseSigma: 4.0,
    hotPixelsCount: 2,
    blurRadiusPx: 1,
    dropProbability: 0.02
  },
  MED: {
    name: 'Med',
    wanderRmsPx: 2.5,
    wanderCornerHz: 2.0,
    scintillationSigma: 0.35,
    jitterRmsDeg: 0.15,
    vibrationHz: 10.0,
    noiseSigma: 10.0,
    hotPixelsCount: 6,
    blurRadiusPx: 2,
    dropProbability: 0.05
  },
  HIGH: {
    name: 'High',
    wanderRmsPx: 6.0,
    wanderCornerHz: 3.0,
    scintillationSigma: 0.75,
    jitterRmsDeg: 0.48,
    vibrationHz: 12.0,
    noiseSigma: 22.0,
    hotPixelsCount: 18,
    blurRadiusPx: 3,
    dropProbability: 0.18
  }
};

