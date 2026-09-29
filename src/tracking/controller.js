import { CONTROLLER_CONFIG, CAMERA_CONFIG, SLEW_PRESETS } from './config.js';
import { angularDiffDeg } from './geometry.js';

/**
 * Creates the line-of-sight tracking PID controller with feed-forward and anti-windup.
 * Commands angular rates (deg/s) to the gimbal servo.
 *
 * @param {Object} [config=CONTROLLER_CONFIG]
 * @returns {Object} Controller instance
 */
export function createController(config = CONTROLLER_CONFIG) {
  const cfg = { ...CONTROLLER_CONFIG, ...config };

  let intPan = 0;
  let intTilt = 0;
  let prevPanErr = 0;
  let prevTiltErr = 0;
  let filtDerivPan = 0;
  let filtDerivTilt = 0;
  let hasPrev = false;

  /**
   * Reset integrator and filter states.
   */
  function reset() {
    intPan = 0;
    intTilt = 0;
    prevPanErr = 0;
    prevTiltErr = 0;
    filtDerivPan = 0;
    filtDerivTilt = 0;
    hasPrev = false;
  }

  /**
   * Advance controller by fixed timestep dt.
   *
   * @param {number} dt - Timestep in seconds
   * @param {Object} inputs
   * @param {number} inputs.gimbalPanDeg - Current gimbal pan angle in degrees
   * @param {number} inputs.gimbalTiltDeg - Current gimbal tilt angle in degrees
   * @param {{ panDeg: number, tiltDeg: number }} inputs.losEstimate - Target line-of-sight angles
   * @param {{ panRateDegS: number, tiltRateDegS: number }} [inputs.losRateEstimate] - Target LOS angular rates
   * @param {string} [inputs.mode='TRACK'] - Active tracking state mode
   * @param {number} [inputs.maxSlewRate] - Optional slew velocity limit override in deg/s
   * @returns {{ panRateDegS: number, tiltRateDegS: number, panErrDeg: number, tiltErrDeg: number }}
   */
  function step(dt, inputs) {
    if (dt <= 0) return { panRateDegS: 0, tiltRateDegS: 0, panErrDeg: 0, tiltErrDeg: 0 };

    const {
      gimbalPanDeg,
      gimbalTiltDeg,
      losEstimate,
      losRateEstimate = { panRateDegS: 0, tiltRateDegS: 0 }
    } = inputs;

    const preset = CAMERA_CONFIG.activeSlewPreset || 'baseline';
    const vmax = inputs.maxSlewRate ?? SLEW_PRESETS[preset] ?? CAMERA_CONFIG.maxSlewRateDegPerSec ?? 45;

    const kp = cfg.kp ?? 4.0;
    const ki = cfg.ki ?? 0.5;
    const kd = cfg.kd ?? 0.2;
    const kff = cfg.kff ?? 1.0;
    const alpha = cfg.dFilterAlpha ?? 0.2;
    const maxInt = (cfg.integralClampDegS ?? 15.0) / Math.max(ki, 1e-4);

    // Shortest angular difference
    const panErr = angularDiffDeg(losEstimate.panDeg, gimbalPanDeg);
    const tiltErr = losEstimate.tiltDeg - gimbalTiltDeg;

    // Filtered derivative
    if (!hasPrev) {
      prevPanErr = panErr;
      prevTiltErr = tiltErr;
      filtDerivPan = 0;
      filtDerivTilt = 0;
      hasPrev = true;
    }

    const rawDPan = (panErr - prevPanErr) / dt;
    const rawDTilt = (tiltErr - prevTiltErr) / dt;

    filtDerivPan = alpha * rawDPan + (1 - alpha) * filtDerivPan;
    filtDerivTilt = alpha * rawDTilt + (1 - alpha) * filtDerivTilt;

    prevPanErr = panErr;
    prevTiltErr = tiltErr;

    // Anti-windup conditional integration:
    // Only integrate if not saturated, or if error opposes current integral
    const tentativeIntPan = Math.max(-maxInt, Math.min(maxInt, intPan + panErr * dt));
    const tentativeIntTilt = Math.max(-maxInt, Math.min(maxInt, intTilt + tiltErr * dt));

    // Raw unconstrained command
    let panCmd = kp * panErr + ki * tentativeIntPan + kd * filtDerivPan + kff * (losRateEstimate.panRateDegS || 0);
    let tiltCmd = kp * tiltErr + ki * tentativeIntTilt + kd * filtDerivTilt + kff * (losRateEstimate.tiltRateDegS || 0);

    // Apply conditional integration based on saturation
    if (Math.abs(panCmd) < vmax || Math.sign(panErr) !== Math.sign(panCmd)) {
      intPan = tentativeIntPan;
    }
    if (Math.abs(tiltCmd) < vmax || Math.sign(tiltErr) !== Math.sign(tiltCmd)) {
      intTilt = tentativeIntTilt;
    }

    // Output rate clamping
    const panRateDegS = Math.max(-vmax, Math.min(vmax, panCmd));
    const tiltRateDegS = Math.max(-vmax, Math.min(vmax, tiltCmd));

    return {
      panRateDegS,
      tiltRateDegS,
      panErrDeg: panErr,
      tiltErrDeg: tiltErr
    };
  }

  return {
    step,
    reset
  };
}
