import { CAMERA_CONFIG, TRACKING_CONFIG, SLEW_PRESETS } from './config.js';
import { wrapDeg } from './geometry.js';

/**
 * Compute the continuous raster search scan setpoint.
 *
 * Sweeps pan 360° continuously in horizontal rows whose pitch is FOV * (1 - overlap),
 * alternating sweep direction across rows, covering tilt between ±tiltScanLimitDeg.
 *
 * @param {number} elapsedSec - Elapsed simulation time in SEARCH state
 * @param {Object} [config={}] - Configuration overrides
 * @returns {{ panDeg: number, tiltDeg: number, cycleDurationSec: number, rowIndex: number, totalRows: number }}
 */
export function raster(elapsedSec, config = {}) {
  const fov = config.fovDeg ?? CAMERA_CONFIG.fovDeg ?? 20;
  const overlap = config.overlap ?? TRACKING_CONFIG.overlap ?? 0.2;
  const tiltLimit = config.tiltScanLimitDeg ?? TRACKING_CONFIG.tiltScanLimitDeg ?? 55;

  const preset = config.activeSlewPreset ?? CAMERA_CONFIG.activeSlewPreset ?? 'baseline';
  const maxSlew = SLEW_PRESETS[preset] ?? CAMERA_CONFIG.maxSlewRateDegPerSec ?? 45;
  const scanRate = Math.min(config.scanRateDegS ?? TRACKING_CONFIG.scanRateDegS ?? 35, maxSlew);

  const rowPitch = fov * (1 - overlap); // e.g. 20 * 0.8 = 16 deg
  const totalTiltSpan = tiltLimit * 2;
  const numSteps = Math.ceil(totalTiltSpan / rowPitch);
  const totalRows = numSteps + 1; // inclusive rows from -tiltLimit to +tiltLimit
  const effectivePitch = totalTiltSpan / numSteps;

  const timePerRow = 360 / Math.max(1, scanRate);
  const cycleDurationSec = totalRows * timePerRow;

  const t = Math.max(0, elapsedSec) % cycleDurationSec;
  const rowIndex = Math.min(totalRows - 1, Math.floor(t / timePerRow));
  const rowProgress = (t % timePerRow) / timePerRow; // [0, 1)

  // Tilt for current row
  const tiltDeg = -tiltLimit + rowIndex * effectivePitch;

  // Alternate pan direction
  let panDeg;
  if (rowIndex % 2 === 0) {
    // Left-to-right: -180 to +180
    panDeg = -180 + rowProgress * 360;
  } else {
    // Right-to-left: +180 to -180
    panDeg = 180 - rowProgress * 360;
  }

  return {
    panDeg: wrapDeg(panDeg),
    tiltDeg: Math.max(-90, Math.min(90, tiltDeg)),
    cycleDurationSec,
    rowIndex,
    totalRows
  };
}

/**
 * Compute the expanding Archimedean spiral reacquisition search setpoint.
 *
 * @param {number} elapsedSec - Elapsed simulation time in REACQUIRE state
 * @param {{ panDeg: number, tiltDeg: number }} center - Center of the search (last Kalman estimate)
 * @param {Object} [config={}] - Configuration overrides
 * @returns {{ panDeg: number, tiltDeg: number, radiusDeg: number, done: boolean }}
 */
export function spiral(elapsedSec, center, config = {}) {
  const fov = config.fovDeg ?? CAMERA_CONFIG.fovDeg ?? 20;
  const overlap = config.overlap ?? TRACKING_CONFIG.overlap ?? 0.2;
  const maxRadius = config.reacquireMaxRadiusDeg ?? TRACKING_CONFIG.reacquireMaxRadiusDeg ?? 45;

  const preset = config.activeSlewPreset ?? CAMERA_CONFIG.activeSlewPreset ?? 'baseline';
  const maxSlew = SLEW_PRESETS[preset] ?? CAMERA_CONFIG.maxSlewRateDegPerSec ?? 45;
  const scanRate = Math.min(config.scanRateDegS ?? TRACKING_CONFIG.scanRateDegS ?? 35, maxSlew);

  const radialPitch = fov * (1 - overlap); // distance between successive spiral arms
  const b = radialPitch / (2 * Math.PI); // r = b * theta

  const t = Math.max(0, elapsedSec);

  // theta(t) for constant speed scanRate along spiral: theta = sqrt(2 * scanRate * t / b)
  const theta = Math.sqrt((2 * scanRate * t) / Math.max(1e-4, b));
  const r = b * theta;

  if (r >= maxRadius) {
    return {
      panDeg: wrapDeg(center ? center.panDeg : 0),
      tiltDeg: center ? center.tiltDeg : 0,
      radiusDeg: maxRadius,
      done: true
    };
  }

  const dPan = r * Math.cos(theta);
  const dTilt = r * Math.sin(theta);

  const centerPan = center ? center.panDeg : 0;
  const centerTilt = center ? center.tiltDeg : 0;

  return {
    panDeg: wrapDeg(centerPan + dPan),
    tiltDeg: Math.max(-90, Math.min(90, centerTilt + dTilt)),
    radiusDeg: r,
    done: false
  };
}
