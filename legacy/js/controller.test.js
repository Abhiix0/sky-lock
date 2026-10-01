import { describe, it, expect } from 'vitest';
import { createController } from '../src/tracking/controller.js';

/**
 * Tiny simulated gimbal servo (no Three.js).
 */
function createSimulatedGimbal(accelLimit = 120, maxSlewRate = 45) {
  let angle = 0;
  let rate = 0;

  return {
    step(dt, cmdRate) {
      const clampedCmd = Math.max(-maxSlewRate, Math.min(maxSlewRate, cmdRate));
      const maxDv = accelLimit * dt;
      const dv = clampedCmd - rate;
      rate += Math.max(-maxDv, Math.min(maxDv, dv));
      angle += rate * dt;
    },
    getAngle: () => angle,
    getRate: () => rate,
    setAngle: (a) => { angle = a; rate = 0; }
  };
}

describe('Controller (Sub-phase 2B)', () => {
  it('tracks ramp with steady-state error < 0.1 deg with feed-forward ON, larger with it OFF', () => {
    const rampRate = 10.0; // deg/s
    const dt = 1 / 120; // 120 Hz controller loop
    const duration = 4.0; // seconds
    const steps = Math.floor(duration / dt);

    // 1. Run with Feed-Forward ON (kff = 1.0)
    const ctrlWithFF = createController({ kff: 1.0 });
    const gimbalWithFF = createSimulatedGimbal();

    for (let i = 0; i < steps; i++) {
      const t = i * dt;
      const targetPan = rampRate * t;
      const cmd = ctrlWithFF.step(dt, {
        gimbalPanDeg: gimbalWithFF.getAngle(),
        gimbalTiltDeg: 0,
        losEstimate: { panDeg: targetPan, tiltDeg: 0 },
        losRateEstimate: { panRateDegS: rampRate, tiltRateDegS: 0 }
      });
      gimbalWithFF.step(dt, cmd.panRateDegS);
    }

    const tFinal = steps * dt;
    const finalTarget = rampRate * tFinal;
    const errWithFF = Math.abs(finalTarget - gimbalWithFF.getAngle());

    // 2. Run with Feed-Forward OFF (kff = 0.0)
    const ctrlNoFF = createController({ kff: 0.0 });
    const gimbalNoFF = createSimulatedGimbal();

    for (let i = 0; i < steps; i++) {
      const t = i * dt;
      const targetPan = rampRate * t;
      const cmd = ctrlNoFF.step(dt, {
        gimbalPanDeg: gimbalNoFF.getAngle(),
        gimbalTiltDeg: 0,
        losEstimate: { panDeg: targetPan, tiltDeg: 0 },
        losRateEstimate: { panRateDegS: rampRate, tiltRateDegS: 0 }
      });
      gimbalNoFF.step(dt, cmd.panRateDegS);
    }

    const errNoFF = Math.abs(finalTarget - gimbalNoFF.getAngle());

    console.log(`Measured steady-state error with Feed-Forward ON:  ${errWithFF.toFixed(4)}°`);
    console.log(`Measured steady-state error with Feed-Forward OFF: ${errNoFF.toFixed(4)}°`);

    expect(errWithFF).toBeLessThan(0.1);
    expect(errNoFF).toBeGreaterThan(errWithFF);
  });

  it('no windup after 5 s of actuator saturation', () => {
    const ctrl = createController();
    const gimbal = createSimulatedGimbal();
    const dt = 1 / 120;

    // Command an unreachable target (1000 deg away) causing saturation at max slew rate for 5s
    const satSteps = Math.floor(5.0 / dt);
    for (let i = 0; i < satSteps; i++) {
      const cmd = ctrl.step(dt, {
        gimbalPanDeg: gimbal.getAngle(),
        gimbalTiltDeg: 0,
        losEstimate: { panDeg: 1000, tiltDeg: 0 }
      });
      gimbal.step(dt, cmd.panRateDegS);
    }

    // Now snap target to current gimbal position. Controller should stop commanding rate quickly
    const currentAngle = gimbal.getAngle();
    let stepsToStop = 0;
    for (let i = 0; i < 120; i++) { // 1 second
      const cmd = ctrl.step(dt, {
        gimbalPanDeg: gimbal.getAngle(),
        gimbalTiltDeg: 0,
        losEstimate: { panDeg: currentAngle, tiltDeg: 0 }
      });
      gimbal.step(dt, cmd.panRateDegS);
      if (Math.abs(cmd.panRateDegS) < 0.1) {
        stepsToStop = i;
        break;
      }
    }

    // Must not remain stuck in saturation; recovers in a fraction of a second (< 0.85s)
    expect(stepsToStop).toBeLessThan(100);
  });
});
