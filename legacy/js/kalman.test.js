import { describe, it, expect } from 'vitest';
import { createKalmanFilter } from '../src/tracking/kalman.js';
import { wrapDeg, angularDiffDeg } from '../src/tracking/geometry.js';

describe('Kalman Filter (Sub-phase 2B)', () => {
  it('converges on a constant-rate target', () => {
    const kf = createKalmanFilter();
    const truePanRate = 12.0; // deg/s
    const trueTiltRate = -4.0; // deg/s
    let t = 0;
    const dt = 1 / 30; // 30 Hz feed

    kf.init(10.0, 5.0, 0);

    for (let i = 1; i <= 60; i++) { // 2 seconds
      t += dt;
      const truePan = 10.0 + truePanRate * t;
      const trueTilt = 5.0 + trueTiltRate * t;
      kf.update(truePan, trueTilt, t);
    }

    const state = kf.getState();
    expect(Math.abs(state.panRateDegS - truePanRate)).toBeLessThan(0.01);
    expect(Math.abs(state.tiltRateDegS - trueTiltRate)).toBeLessThan(0.01);
  });

  it('survives ±180° seam crossing without jump', () => {
    const kf = createKalmanFilter();
    let t = 0;
    const dt = 1 / 30;
    const panRate = 15.0; // moves 15 deg/s across 180° seam
    let currentPan = 175.0;

    kf.init(currentPan, 0, 0);

    for (let i = 1; i <= 30; i++) { // crosses 180 within ~10 steps
      t += dt;
      currentPan += panRate * dt;
      const wrappedMeasPan = wrapDeg(currentPan);

      kf.update(wrappedMeasPan, 0, t);
      const st = kf.getState();

      // Shortest difference between estimated and true unwrapped pan
      const diff = Math.abs(angularDiffDeg(st.panDeg, wrappedMeasPan));
      expect(diff).toBeLessThan(0.5);
    }
  });

  it('sigma grows during prediction-only coasting', () => {
    const kf = createKalmanFilter();
    kf.init(0, 0, 0);
    kf.update(0.1, 0, 0.033);
    kf.update(0.2, 0, 0.066);

    const initialSigma = kf.getPositionSigmaDeg();

    // Coast for 5 seconds without updates
    kf.predict(5.0);
    const coastingSigma = kf.getPositionSigmaDeg();

    expect(coastingSigma).toBeGreaterThan(initialSigma * 5);
  });

  it('a 5-sigma outlier is rejected by the innovation gate', () => {
    const kf = createKalmanFilter();
    kf.init(0, 0, 0);
    for (let i = 1; i <= 30; i++) {
      kf.update(0.01 * i, 0, i * 0.033);
    }

    const sigma = kf.getPositionSigmaDeg();
    // In-gate measurement (1 sigma off)
    const inGateDist = kf.getInnovationGate(0.3 + sigma, 0);
    expect(inGateDist).toBeLessThan(4.0);

    // 5-sigma outlier
    const outlierDist = kf.getInnovationGate(0.3 + sigma * 5.5, 0);
    expect(outlierDist).toBeGreaterThan(4.5);
  });
});
