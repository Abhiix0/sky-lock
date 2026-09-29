import { CAMERA_CONFIG, SLEW_PRESETS } from './config.js';

/**
 * Wraps angle to (-180, 180] degrees.
 *
 * @param {number} deg
 * @returns {number}
 */
export function wrapDeg(deg) {
  let a = (deg + 180) % 360;
  if (a <= 0) a += 360;
  return a - 180;
}

/**
 * Shortest signed angular difference from current to target in (-180, 180] degrees.
 *
 * @param {number} targetDeg
 * @param {number} currentDeg
 * @returns {number}
 */
export function angularDiffDeg(targetDeg, currentDeg) {
  return wrapDeg(targetDeg - currentDeg);
}

/**
 * Creates the physically limited 2-axis gimbal servo controller.
 *
 * @param {Object} virtualCamera - Virtual camera instance with setPanTilt/getPanTilt
 * @param {Object} [config=CAMERA_CONFIG] - Camera & gimbal configuration
 * @returns {Object} Gimbal controller API
 */
export function createGimbal(virtualCamera, config = CAMERA_CONFIG) {
  const panLimit = config.panLimitDeg ?? 180;
  const tiltLimit = config.tiltLimitDeg ?? 90;
  const panWrap = config.panWrap ?? true;
  const accelLimit = config.maxSlewAccelDegPerSec2 ?? 120;

  // Initialize state from virtual camera
  const initialPose = virtualCamera ? virtualCamera.getPanTilt() : { panDeg: 90, tiltDeg: 0 };
  let pan = initialPose.panDeg;
  let tilt = initialPose.tiltDeg;
  let panRate = 0;
  let tiltRate = 0;

  let mode = 'GOTO'; // 'GOTO' | 'RATE'
  let targetPan = pan;
  let targetTilt = tilt;
  let cmdPanRate = 0;
  let cmdTiltRate = 0;

  let atLimitPan = false;
  let atLimitTilt = false;

  /**
   * Get effective maximum slew velocity based on active slew preset.
   *
   * @returns {number} deg/s
   */
  function getMaxSlewRate() {
    const preset = config.activeSlewPreset || 'baseline';
    return SLEW_PRESETS[preset] ?? config.maxSlewRateDegPerSec ?? 45;
  }

  /**
   * Command target angles for go-to mode.
   *
   * @param {number} panDeg - Desired pan in degrees
   * @param {number} tiltDeg - Desired tilt in degrees
   */
  function setGimbalCommand(panDeg, tiltDeg) {
    mode = 'GOTO';
    targetPan = panWrap ? wrapDeg(panDeg) : Math.max(-panLimit, Math.min(panLimit, panDeg));
    targetTilt = Math.max(-tiltLimit, Math.min(tiltLimit, tiltDeg));
  }

  /**
   * Command angular rates for rate mode.
   *
   * @param {number} panRateDegS - Desired pan rate in deg/s
   * @param {number} tiltRateDegS - Desired tilt rate in deg/s
   */
  function setGimbalRateCommand(panRateDegS, tiltRateDegS) {
    mode = 'RATE';
    cmdPanRate = panRateDegS;
    cmdTiltRate = tiltRateDegS;
  }

  /**
   * Instantly snap gimbal to angles (debug/reset only).
   *
   * @param {number} panDeg
   * @param {number} tiltDeg
   */
  function snapTo(panDeg, tiltDeg) {
    pan = panWrap ? wrapDeg(panDeg) : Math.max(-panLimit, Math.min(panLimit, panDeg));
    tilt = Math.max(-tiltLimit, Math.min(tiltLimit, tiltDeg));
    panRate = 0;
    tiltRate = 0;
    targetPan = pan;
    targetTilt = tilt;
    cmdPanRate = 0;
    cmdTiltRate = 0;
    if (virtualCamera) {
      virtualCamera.setPanTilt(pan, tilt);
    }
  }

  /**
   * Advance gimbal servo dynamics by fixed timestep dt.
   *
   * @param {number} dt - Timestep in seconds
   */
  function step(dt) {
    if (dt <= 0) return;

    const vmax = getMaxSlewRate();
    const a = accelLimit;
    const maxDv = a * dt;

    // --- PAN AXIS ---
    let desiredPanVel;
    if (mode === 'GOTO') {
      const err = panWrap ? angularDiffDeg(targetPan, pan) : (targetPan - pan);
      const absErr = Math.abs(err);
      if (absErr < 0.0001 && Math.abs(panRate) < 0.001) {
        pan = targetPan;
        panRate = 0;
        desiredPanVel = 0;
      } else {
        // desiredVel = sign(err)*min(vmax, sqrt(2*a*|err|))
        desiredPanVel = Math.sign(err) * Math.min(vmax, Math.sqrt(Math.max(0, 2 * a * absErr)));
      }
    } else {
      desiredPanVel = Math.max(-vmax, Math.min(vmax, cmdPanRate));
    }

    const dPanV = desiredPanVel - panRate;
    panRate += Math.max(-maxDv, Math.min(maxDv, dPanV));
    pan += panRate * dt;

    if (panWrap) {
      pan = wrapDeg(pan);
      atLimitPan = false;
    } else {
      if (pan >= panLimit) {
        pan = panLimit;
        atLimitPan = true;
        if (panRate > 0) panRate = 0;
      } else if (pan <= -panLimit) {
        pan = -panLimit;
        atLimitPan = true;
        if (panRate < 0) panRate = 0;
      } else {
        atLimitPan = false;
      }
    }

    // --- TILT AXIS ---
    let desiredTiltVel;
    if (mode === 'GOTO') {
      const err = targetTilt - tilt;
      const absErr = Math.abs(err);
      if (absErr < 0.0001 && Math.abs(tiltRate) < 0.001) {
        tilt = targetTilt;
        tiltRate = 0;
        desiredTiltVel = 0;
      } else {
        desiredTiltVel = Math.sign(err) * Math.min(vmax, Math.sqrt(Math.max(0, 2 * a * absErr)));
      }
    } else {
      desiredTiltVel = Math.max(-vmax, Math.min(vmax, cmdTiltRate));
    }

    const dTiltV = desiredTiltVel - tiltRate;
    tiltRate += Math.max(-maxDv, Math.min(maxDv, dTiltV));
    tilt += tiltRate * dt;

    if (tilt >= tiltLimit) {
      tilt = tiltLimit;
      atLimitTilt = true;
      if (tiltRate > 0) tiltRate = 0;
    } else if (tilt <= -tiltLimit) {
      tilt = -tiltLimit;
      atLimitTilt = true;
      if (tiltRate < 0) tiltRate = 0;
    } else {
      atLimitTilt = false;
    }

    if (virtualCamera) {
      virtualCamera.setPanTilt(pan, tilt);
    }
  }

  /**
   * Return current gimbal state.
   *
   * @returns {{ panDeg: number, tiltDeg: number, panRateDegS: number, tiltRateDegS: number, mode: string, atLimitPan: boolean, atLimitTilt: boolean }}
   */
  function getGimbalState() {
    return {
      panDeg: pan,
      tiltDeg: tilt,
      panRateDegS: panRate,
      tiltRateDegS: tiltRate,
      mode,
      atLimitPan,
      atLimitTilt
    };
  }

  return {
    setGimbalCommand,
    setGimbalRateCommand,
    step,
    getGimbalState,
    snapTo
  };
}

/**
 * Self-test routine for gimbal servo response and seam crossing.
 *
 * @param {Object} [gimbalInstance]
 * @param {number} [dt=1/120]
 * @returns {{ maxRate: number, maxAccel: number, overshootDeg: number, seamPathDeg: number }}
 */
export function runGimbalSelfTest(gimbalInstance, dt = 1 / 120) {
  // Use a mock camera or local gimbal if not passed
  let localPan = 0;
  let localTilt = 0;
  const mockCam = {
    setPanTilt: (p, t) => { localPan = p; localTilt = t; },
    getPanTilt: () => ({ panDeg: localPan, tiltDeg: localTilt })
  };

  const testGimbal = gimbalInstance || createGimbal(mockCam, CAMERA_CONFIG);

  // Test 1: 90 degree pan step from 0 to 90
  testGimbal.snapTo(0, 0);
  testGimbal.setGimbalCommand(90, 0);

  let maxRate = 0;
  let maxAccel = 0;
  let prevRate = 0;
  let maxPanObserved = 0;

  for (let i = 0; i < 600; i++) { // up to 5 seconds
    testGimbal.step(dt);
    const st = testGimbal.getGimbalState();
    const rate = Math.abs(st.panRateDegS);
    if (rate > maxRate) maxRate = rate;

    const accel = Math.abs(rate - prevRate) / dt;
    if (accel > maxAccel) maxAccel = accel;
    prevRate = rate;

    if (st.panDeg > maxPanObserved) maxPanObserved = st.panDeg;
    if (Math.abs(st.panDeg - 90) < 0.001 && rate < 0.001) break;
  }

  const overshootDeg = Math.max(0, maxPanObserved - 90);

  // Test 2: Seam crossing from 179 to -179
  testGimbal.snapTo(179, 0);
  testGimbal.setGimbalCommand(-179, 0);

  let totalPathDeg = 0;
  let lastP = 179;

  for (let i = 0; i < 240; i++) {
    testGimbal.step(dt);
    const st = testGimbal.getGimbalState();
    const dp = Math.abs(angularDiffDeg(st.panDeg, lastP));
    totalPathDeg += dp;
    lastP = st.panDeg;
    if (Math.abs(angularDiffDeg(-179, st.panDeg)) < 0.01 && Math.abs(st.panRateDegS) < 0.01) break;
  }

  return {
    maxRate,
    maxAccel,
    overshootDeg,
    seamPathDeg: totalPathDeg
  };
}
