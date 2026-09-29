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

  it('12s blackout goes TRACK -> LOST -> REACQUIRE -> ACQUIRE -> TRACK', () => {
    const sm = createStateMachine({ lostMissFrames: 5, coastMaxSec: 10.0, acquireConfirmFrames: 3 });
    const kalman = createKalmanFilter();
    let gimbalState = { panDeg: 10, tiltDeg: 0, panRateDegS: 0, tiltRateDegS: 0 };

    // Reach TRACK at t = 1s
    sm.update({ simTime: 1.0, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 1.033, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    sm.update({ simTime: 1.066, detections: [{ cx: 320, cy: 240, snr: 10 }], kalman, gimbalState });
    expect(sm.getState()).toBe('TRACK');

    // Blackout begins: 6 misses (at 30 Hz ~ 0.2s)
    let t = 1.1;
    for (let i = 0; i < 6; i++) {
      t += 0.033;
      sm.update({ simTime: t, detections: [], kalman, gimbalState });
    }
    expect(sm.getState()).toBe('LOST');

    // Coasting for 10.5 seconds in blackout
    t += 10.5;
    sm.update({ simTime: t, detections: [], kalman, gimbalState });
    expect(sm.getState()).toBe('REACQUIRE');

    // Detection reappears in REACQUIRE spiral!
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
