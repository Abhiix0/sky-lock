import { describe, it, expect } from 'vitest';
import { createMetrics } from '../src/tracking/metrics.js';

describe('Metrics Module (Sub-phase 3C)', () => {
  it('computes acquisition time and tracking errors from scripted samples', () => {
    const metrics = createMetrics();

    // 0s to 5s: unobservable (e.g. Earth occultation at scenario start)
    for (let t = 0.0; t <= 5.0; t += 0.1) {
      metrics.addSample({
        simTime: t,
        state: 'SEARCH',
        groundTruth: { pixelX: 0, pixelY: 0, inFrustum: false, losClear: false, reachable: true },
        procMs: 1.5,
        fps: 60
      });
    }

    // 5.1s to 7.0s: observable, in SEARCH/ACQUIRE
    for (let t = 5.1; t <= 7.0; t += 0.1) {
      metrics.addSample({
        simTime: t,
        state: t < 6.5 ? 'SEARCH' : 'ACQUIRE',
        groundTruth: { pixelX: 340, pixelY: 260, inFrustum: true, losClear: true, reachable: true },
        procMs: 2.0,
        fps: 60
      });
    }

    // 7.1s to 12.0s: in TRACK with target near center (325, 245)
    // image center is (320, 240), so pointing error is hypot(5, 5) = sqrt(50) = 7.07 px
    for (let t = 7.1; t <= 12.0; t += 0.1) {
      metrics.addSample({
        simTime: t,
        state: 'TRACK',
        groundTruth: { pixelX: 325, pixelY: 245, inFrustum: true, losClear: true, reachable: true },
        estimatePx: { x: 324, y: 246 },
        procMs: 2.5,
        fps: 60
      });
    }

    const summary = metrics.getSummary();

    // First observable was at ~5.1s
    expect(summary.firstObservableTime).toBeCloseTo(5.1, 1);
    // First track was at ~7.1s
    expect(summary.firstTrackTime).toBeCloseTo(7.1, 1);
    // Acquisition time = 7.1 - 5.1 = 2.0s
    expect(summary.acquisitionTimeSec).toBeCloseTo(2.0, 1);
    expect(summary.acquisitionFromStartSec).toBeCloseTo(7.1, 1);

    // Pointing error should be ~7.07 px
    expect(summary.pointingError.meanPx).toBeCloseTo(Math.hypot(5, 5), 1);
    expect(summary.pointingError.rmsPx).toBeCloseTo(Math.hypot(5, 5), 1);

    // Tracking error from estimate (324, 246) to gt (325, 245) is hypot(1, -1) = 1.414 px
    expect(summary.trackingError.meanPx).toBeCloseTo(Math.SQRT2, 1);

    // In-track pointing error 7.07 px < lockRadiusPx (30 px) -> lock retention should be high
    expect(summary.lockRetentionRate).toBeGreaterThan(60); // 5s in track out of 7s observable
  });

  it('computes reacquisition time on simulated occlusion', () => {
    const metrics = createMetrics();

    // Step 1: Initial TRACK for 10 seconds (simTime 0 to 10)
    for (let t = 0.0; t <= 10.0; t += 0.1) {
      metrics.addSample({
        simTime: t,
        state: 'TRACK',
        groundTruth: { pixelX: 320, pixelY: 240, inFrustum: true, losClear: true, reachable: true }
      });
    }

    // Step 2: Occlusion occurs at t = 10.1s to 20.0s (losClear = false), state drops to LOST then REACQUIRE
    for (let t = 10.1; t <= 20.0; t += 0.1) {
      metrics.addSample({
        simTime: t,
        state: t < 12.0 ? 'LOST' : 'REACQUIRE',
        groundTruth: { pixelX: 0, pixelY: 0, inFrustum: false, losClear: false, reachable: true }
      });
    }

    // Step 3: Target emerges at t = 20.1s (losClear = true). Still searching until t = 22.5s
    for (let t = 20.1; t < 22.5; t += 0.1) {
      metrics.addSample({
        simTime: t,
        state: 'REACQUIRE',
        groundTruth: { pixelX: 350, pixelY: 250, inFrustum: true, losClear: true, reachable: true }
      });
    }

    // Step 4: Re-enters TRACK at t = 22.5s!
    // Expected reacquisition duration = 22.5 - 20.1 = 2.4s
    for (let t = 22.5; t <= 30.0; t += 0.1) {
      metrics.addSample({
        simTime: t,
        state: 'TRACK',
        groundTruth: { pixelX: 321, pixelY: 241, inFrustum: true, losClear: true, reachable: true }
      });
    }

    const summary = metrics.getSummary();
    expect(summary.reacquisitions.length).toBe(1);
    expect(summary.reacquisitionMeanSec).toBeCloseTo(2.4, 1);
    expect(summary.reacquisitionMaxSec).toBeCloseTo(2.4, 1);
  });

  it('detects false locks when estimate is far from ground truth for > 1.0s', () => {
    const metrics = createMetrics({ falseLockPx: 50 });

    // In TRACK for 2.0s with huge pointing error (120 px > 50 px)
    for (let t = 0.0; t <= 2.0; t += 0.1) {
      metrics.addSample({
        simTime: t,
        state: 'TRACK',
        groundTruth: { pixelX: 440, pixelY: 240, inFrustum: true, losClear: true, reachable: true }, // 120 px from 320
        estimatePx: { x: 320, y: 240 }
      });
    }

    const summary = metrics.getSummary();
    expect(summary.falseLocks).toBe(1);
  });
});
