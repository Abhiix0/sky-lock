import { KALMAN_CONFIG } from './config.js';
import { wrapDeg, angularDiffDeg } from './geometry.js';

/**
 * Constant-velocity Kalman Filter for 2D body-frame Line-of-Sight tracking.
 * State vector: [pan, tilt, panRate, tiltRate]^T (in degrees and deg/s).
 *
 * Pan angle state is kept continuous (unwrapped) across the ±180° seam to prevent
 * covariance divergence or state jumps.
 *
 * @param {Object} [config=KALMAN_CONFIG]
 * @returns {Object} Kalman tracker instance
 */
export function createKalmanFilter(config = KALMAN_CONFIG) {
  const cfg = { ...KALMAN_CONFIG, ...config };

  // State: [pan, tilt, panRate, tiltRate]
  const x = new Float64Array(4);

  // Covariance matrix 4x4 stored in row-major order
  const P = new Float64Array(16);

  let lastTime = 0;
  let isInitialized = false;

  /**
   * Reset covariance matrix with initial uncertainty.
   */
  function resetCovariance() {
    P.fill(0);
    const rMeas = cfg.rMeasDeg || 0.1;
    P[0] = rMeas * rMeas; // var(pan)
    P[5] = rMeas * rMeas; // var(tilt)
    P[10] = 400.0; // var(panRate) ~ 20 deg/s sigma
    P[15] = 400.0; // var(tiltRate) ~ 20 deg/s sigma
  }

  /**
   * Initialize filter state with first measurement.
   *
   * @param {number} measPan - Measured pan in degrees
   * @param {number} measTilt - Measured tilt in degrees
   * @param {number} t - Simulation time in seconds
   */
  function init(measPan, measTilt, t) {
    x[0] = measPan;
    x[1] = measTilt;
    x[2] = 0;
    x[3] = 0;
    resetCovariance();
    lastTime = t;
    isInitialized = true;
  }

  /**
   * Predict state and propagate covariance forward to time t.
   *
   * @param {number} t - Target simulation time in seconds
   */
  function predict(t) {
    if (!isInitialized) return;
    const dt = t - lastTime;
    if (dt <= 0) return;

    // State transition F:
    // x_new = x + dt * vx
    // y_new = y + dt * vy
    x[0] += dt * x[2];
    x[1] += dt * x[3];

    // Discrete white-noise acceleration model:
    // Q_block = q * [[dt^3/3, dt^2/2], [dt^2/2, dt]]
    const q = cfg.qAccelDegS2 || 25.0;
    const dt2 = dt * dt;
    const dt3 = dt2 * dt;
    const q00 = q * (dt3 / 3);
    const q01 = q * (dt2 / 2);
    const q11 = q * dt;

    // Propagate covariance P = F * P * F^T + Q
    // For decoupled axes (pan: indices 0,2; tilt: indices 1,3):
    const p00 = P[0]; const p02 = P[2];
    const p20 = P[8]; const p22 = P[10];

    P[0] = p00 + dt * (p20 + p02) + dt2 * p22 + q00;
    P[2] = p02 + dt * p22 + q01;
    P[8] = p20 + dt * p22 + q01;
    P[10] = p22 + q11;

    const p11 = P[5]; const p13 = P[7];
    const p31 = P[13]; const p33 = P[15];

    P[5] = p11 + dt * (p31 + p13) + dt2 * p33 + q00;
    P[7] = p13 + dt * p33 + q01;
    P[13] = p31 + dt * p33 + q01;
    P[15] = p33 + q11;

    lastTime = t;
  }

  /**
   * Calculate Mahalanobis distance of a candidate measurement relative to predicted state.
   *
   * @param {number} measPan - Candidate pan in degrees
   * @param {number} measTilt - Candidate tilt in degrees
   * @returns {number} Normalized Mahalanobis distance in standard deviations (sigmas)
   */
  function getInnovationGate(measPan, measTilt) {
    if (!isInitialized) return Infinity;

    // Unwrap measurement relative to unwrapped predicted pan
    const yPan = angularDiffDeg(measPan, x[0]);
    const yTilt = measTilt - x[1];

    const r2 = (cfg.rMeasDeg || 0.1) * (cfg.rMeasDeg || 0.1);
    const s00 = P[0] + r2;
    const s11 = P[5] + r2;

    const d2 = (yPan * yPan) / s00 + (yTilt * yTilt) / s11;
    return Math.sqrt(Math.max(0, d2));
  }

  /**
   * Update filter state with observation at time t.
   *
   * @param {number} measPan - Measured pan in degrees
   * @param {number} measTilt - Measured tilt in degrees
   * @param {number} t - Simulation time in seconds
   */
  function update(measPan, measTilt, t) {
    if (!isInitialized) {
      init(measPan, measTilt, t);
      return;
    }

    predict(t);

    // Innovation y = z - Hx (unwrapped pan error)
    const yPan = angularDiffDeg(measPan, x[0]);
    const yTilt = measTilt - x[1];

    const r2 = (cfg.rMeasDeg || 0.1) * (cfg.rMeasDeg || 0.1);

    // Innovation covariance S = H P H^T + R
    const s00 = P[0] + r2;
    const s11 = P[5] + r2;

    // Kalman gain K = P H^T S^-1
    // Pan axis:
    const k00 = P[0] / s00;
    const k20 = P[8] / s00;

    // Tilt axis:
    const k11 = P[5] / s11;
    const k31 = P[13] / s11;

    // State update x = x + K y
    x[0] += k00 * yPan;
    x[2] += k20 * yPan;
    x[1] += k11 * yTilt;
    x[3] += k31 * yTilt;

    // Covariance update P = (I - K H) P
    // Pan block:
    const p00 = P[0]; const p02 = P[2];
    const p20 = P[8]; const p22 = P[10];

    P[0] = (1 - k00) * p00;
    P[2] = (1 - k00) * p02;
    P[8] = p20 - k20 * p00;
    P[10] = p22 - k20 * p02;

    // Tilt block:
    const p11 = P[5]; const p13 = P[7];
    const p31 = P[13]; const p33 = P[15];

    P[5] = (1 - k11) * p11;
    P[7] = (1 - k11) * p13;
    P[13] = p31 - k31 * p11;
    P[15] = p33 - k31 * p13;
  }

  /**
   * Return current estimated line-of-sight state.
   *
   * @returns {{ panDeg: number, tiltDeg: number, panRateDegS: number, tiltRateDegS: number, unwrappedPanDeg: number }}
   */
  function getState() {
    return {
      panDeg: wrapDeg(x[0]),
      tiltDeg: x[1],
      panRateDegS: x[2],
      tiltRateDegS: x[3],
      unwrappedPanDeg: x[0]
    };
  }

  /**
   * Get predicted line-of-sight state at future time t without advancing filter.
   *
   * @param {number} t - Simulation time in seconds
   * @returns {{ panDeg: number, tiltDeg: number, panRateDegS: number, tiltRateDegS: number }}
   */
  function getPredicted(t) {
    if (!isInitialized) return getState();
    const dt = t - lastTime;
    const predPan = x[0] + dt * x[2];
    const predTilt = x[1] + dt * x[3];
    return {
      panDeg: wrapDeg(predPan),
      tiltDeg: predTilt,
      panRateDegS: x[2],
      tiltRateDegS: x[3]
    };
  }

  /**
   * Get position uncertainty standard deviation in degrees.
   *
   * @returns {number}
   */
  function getPositionSigmaDeg() {
    const rMeas = cfg.rMeasDeg || 0.1;
    return Math.sqrt(Math.max(P[0], P[5]) + (rMeas * rMeas));
  }

  return {
    init,
    predict,
    update,
    getState,
    getPredicted,
    getInnovationGate,
    getPositionSigmaDeg,
    isInitialized: () => isInitialized
  };
}
