import { describe, it, expect } from 'vitest';
import { createStateMachine } from '../src/tracking/stateMachine.js';
import { createKalmanFilter } from '../src/tracking/kalman.js';
import { CAMERA_CONFIG } from '../src/tracking/config.js';

describe('State Machine (Sub-phase 2C)', () => {
  it('clean acquisition: SEARCH -> ACQUIRE -> TRACK', () => {
    const sm = createStateMachine({ acquireConfirmFrames: 3 });
    const kalman = createKalmanFilter();
    const gimbalState = { panDeg: 0, tiltDeg: 0, panRateDegS: 0, tiltRateDegS: 0 };

    expect(sm.getState()).toBe('SEARCH');

    // Frame 1: detection appears in FOV
    const res1 = sm.update({
      simTime: 1.0,
      detections: [{ cx: 320, cy: 240, peak: 200, snr: 10.0, bbox: {} }],
      kalman,
      gimbalState,
      cameraCfg: CAMERA_CONFIG
    });
    expect(res1.state).toBe('ACQUIRE');

    // Frame 2: candidate re-detected (confirm count = 2)
    const res2 = sm.update({
      simTime: 1.033,
      detections: [{ cx: 320, cy: 240, peak: 200, snr: 10.0, bbox: {} }],
      kalman,
      gimbalState,
      cameraCfg: CAMERA_CONFIG
    });
    expect(res2.state).toBe('ACQUIRE');

    // Frame 3: candidate confirmed (confirm count = 3 -> TRACK)
    const res3 = sm.update({
      simTime: 1.066,
      detections: [{ cx: 320, cy: 240, peak: 200, snr: 10.0, bbox: {} }],
      kalman,
      gimbalState,
      cameraCfg: CAMERA_CONFIG
    });
    expect(res3.state).toBe('TRACK');
  });

  it('short dropout (< coast window) maintains/resumes TRACK', () => {
    const sm = createStateMachine({ lostMissFrames: 5 });
    const kalman = createKalmanFilter();
    const gimbalState = { panDeg: 10, tiltDeg: 5, panRateDegS: 0, tiltRateDegS: 0 };

    // Get into TRACK
    sm.update({ simTime: 0.0, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 0.033, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 0.066, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    expect(sm.getState()).toBe('TRACK');

    // 3 missed frames (dropout)
    sm.update({ simTime: 0.1, detections: [], kalman, gimbalState });
    sm.update({ simTime: 0.133, detections: [], kalman, gimbalState });
    sm.update({ simTime: 0.166, detections: [], kalman, gimbalState });
    expect(sm.getState()).toBe('TRACK');

    // Detection returns -> remains in TRACK
    const res = sm.update({
      simTime: 0.2,
      detections: [{ cx: 320, cy: 240, snr: 10 }],
      kalman,
      gimbalState
    });
    expect(res.state).toBe('TRACK');
  });

  it('12s non-occlusion blackout goes TRACK -> LOST -> REACQUIRE -> ACQUIRE -> TRACK', () => {
    const sm = createStateMachine({ lostMissFrames: 5, coastMaxSec: 10.0, acquireConfirmFrames: 3 });
    const kalman = createKalmanFilter();
    let gimbalState = { panDeg: 10, tiltDeg: 0, panRateDegS: 0, tiltRateDegS: 0 };

    // Reach TRACK at t = 1s
    sm.update({ simTime: 1.0, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 1.033, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 1.066, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    expect(sm.getState()).toBe('TRACK');

    // Blackout begins: 6 misses (at 30 Hz ~ 0.2s) — LOS is clear (not occluded)
    let t = 1.1;
    for (let i = 0; i < 6; i++) {
      t += 0.033;
      sm.update({ simTime: t, detections: [], kalman, gimbalState, losOccluded: false });
    }
    expect(sm.getState()).toBe('LOST');

    // Coasting for 10.5 seconds with LOS clear — coast timer counts this time
    t += 10.5;
    sm.update({ simTime: t, detections: [], kalman, gimbalState, losOccluded: false });
    expect(sm.getState()).toBe('REACQUIRE');

    // Detection reappears in REACQUIRE spiral
    t += 0.5;
    const resAcq = sm.update({
      simTime: t,
      detections: [{ cx: 350, cy: 220, snr: 8.0 }],
      kalman,
      gimbalState
    });
    expect(resAcq.state).toBe('ACQUIRE');

    // 2 more detections confirm candidate -> reaches TRACK
    t += 0.033;
    sm.update({ simTime: t, detections: [{ cx: 350, cy: 220, snr: 8.0 }], kalman, gimbalState });
    t += 0.033;
    const resFinal = sm.update({ simTime: t, detections: [{ cx: 350, cy: 220, snr: 8.0 }], kalman, gimbalState });
    expect(resFinal.state).toBe('TRACK');
  });
});

describe('State Machine — Geometric Occlusion (Item 3)', () => {
  it('LOST during geometric occlusion: coast timer frozen, no REACQUIRE transition', () => {
    // Use a short coastMaxSec (5s) so without the fix this would time out quickly
    const sm = createStateMachine({ lostMissFrames: 5, coastMaxSec: 5.0, acquireConfirmFrames: 3 });
    const kalman = createKalmanFilter();
    const gimbalState = { panDeg: 10, tiltDeg: 0, panRateDegS: 0, tiltRateDegS: 0 };

    // Reach TRACK
    sm.update({ simTime: 0.0, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 0.033, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 0.066, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    expect(sm.getState()).toBe('TRACK');

    // 6 misses -> enters LOST at t ~0.3s
    let t = 0.1;
    for (let i = 0; i < 6; i++) {
      t += 0.033;
      sm.update({ simTime: t, detections: [], kalman, gimbalState });
    }
    expect(sm.getState()).toBe('LOST');
    const lostEntryTime = t;

    // Simulate 20 seconds behind Earth (losOccluded = true).
    // coastMaxSec = 5s — without the fix, this would have timed out into REACQUIRE.
    // With the fix, coast timer is frozen: must stay in LOST the whole time.
    for (let elapsed = 0.5; elapsed <= 20; elapsed += 0.5) {
      t = lostEntryTime + elapsed;
      const res = sm.update({ simTime: t, detections: [], kalman, gimbalState, losOccluded: true });
      expect(res.state).toBe('LOST');
    }
  });

  it('LOST transitions to REACQUIRE promptly once LOS clears after occlusion', () => {
    const sm = createStateMachine({ lostMissFrames: 5, coastMaxSec: 5.0, acquireConfirmFrames: 3 });
    const kalman = createKalmanFilter();
    const gimbalState = { panDeg: 10, tiltDeg: 0, panRateDegS: 0, tiltRateDegS: 0 };

    // Reach TRACK then LOST
    sm.update({ simTime: 0.0, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 0.033, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 0.066, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });

    let t = 0.1;
    for (let i = 0; i < 6; i++) {
      t += 0.033;
      sm.update({ simTime: t, detections: [], kalman, gimbalState });
    }
    expect(sm.getState()).toBe('LOST');
    const lostEntryTime = t;

    // 15s behind Earth — coast timer stays frozen
    for (let elapsed = 0.5; elapsed <= 15; elapsed += 0.5) {
      t = lostEntryTime + elapsed;
      sm.update({ simTime: t, detections: [], kalman, gimbalState, losOccluded: true });
    }
    expect(sm.getState()).toBe('LOST'); // still LOST after 15s of occlusion

    // LOS clears. coastMaxSec = 5s. After 5s of clear LOS with no detection -> REACQUIRE.
    const clearTime = t;
    let reacquired = false;
    for (let elapsed = 0.1; elapsed <= 6; elapsed += 0.1) {
      t = clearTime + elapsed;
      const res = sm.update({ simTime: t, detections: [], kalman, gimbalState, losOccluded: false });
      if (res.state === 'REACQUIRE') {
        reacquired = true;
        break;
      }
    }
    expect(reacquired).toBe(true);
  });

  it('non-occlusion coastMaxSec still works normally when losOccluded is false', () => {
    // Verifies original behaviour is unchanged: if LOS is clear but signal is lost,
    // coast timer ticks and REACQUIRE triggers after coastMaxSec.
    const sm = createStateMachine({ lostMissFrames: 5, coastMaxSec: 3.0 });
    const kalman = createKalmanFilter();
    const gimbalState = { panDeg: 5, tiltDeg: 0, panRateDegS: 0, tiltRateDegS: 0 };

    // Reach TRACK
    sm.update({ simTime: 0.0, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 0.033, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 0.066, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });

    // 6 misses -> LOST
    let t = 0.1;
    for (let i = 0; i < 6; i++) {
      t += 0.033;
      sm.update({ simTime: t, detections: [], kalman, gimbalState });
    }
    expect(sm.getState()).toBe('LOST');
    const lostTime = t;

    // 3.5 seconds clear LOS, no detection — must time out into REACQUIRE
    t = lostTime + 3.5;
    const res = sm.update({ simTime: t, detections: [], kalman, gimbalState, losOccluded: false });
    expect(res.state).toBe('REACQUIRE');
  });
});
