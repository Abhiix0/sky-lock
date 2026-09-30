import { describe, it, expect } from 'vitest';
import {
  wrapDeg,
  angularDiffDeg,
  pixelToBodyAngles,
  bodyAnglesToPixel
} from '../src/tracking/geometry.js';
import { CAMERA_CONFIG } from '../src/tracking/config.js';

describe('Geometry (Sub-phase 2B)', () => {
  it('pixel at image center returns exactly the gimbal angles', () => {
    const cx = CAMERA_CONFIG.width / 2;
    const cy = CAMERA_CONFIG.height / 2;

    const testAngles = [
      { pan: 0, tilt: 0 },
      { pan: 45, tilt: 30 },
      { pan: -120, tilt: -45 },
      { pan: 180, tilt: 0 }
    ];

    for (const { pan, tilt } of testAngles) {
      const angles = pixelToBodyAngles(cx, cy, pan, tilt, CAMERA_CONFIG);
      expect(Math.abs(wrapDeg(angles.panDeg - pan))).toBeLessThan(1e-6);
      expect(Math.abs(angles.tiltDeg - tilt)).toBeLessThan(1e-6);
    }
  });

  it('round-trip error between pixelToBodyAngles and bodyAnglesToPixel < 1e-6 deg', () => {
    const testCases = [
      { px: 100, py: 150, pan: 25, tilt: 15 },
      { px: 540, py: 380, pan: -75, tilt: -30 },
      { px: 320, py: 240, pan: 110, tilt: 40 },
      { px: 200, py: 300, pan: 175, tilt: -10 }
    ];

    for (const tc of testCases) {
      const angles = pixelToBodyAngles(tc.px, tc.py, tc.pan, tc.tilt, CAMERA_CONFIG);
      const proj = bodyAnglesToPixel(angles.panDeg, angles.tiltDeg, tc.pan, tc.tilt, CAMERA_CONFIG);

      expect(proj.inFrustum).toBe(true);
      expect(Math.abs(proj.px - tc.px)).toBeLessThan(1e-4);
      expect(Math.abs(proj.py - tc.py)).toBeLessThan(1e-4);

      // Re-convert projected pixel back to angles
      const roundTripAngles = pixelToBodyAngles(proj.px, proj.py, tc.pan, tc.tilt, CAMERA_CONFIG);
      expect(Math.abs(wrapDeg(roundTripAngles.panDeg - angles.panDeg))).toBeLessThan(1e-6);
      expect(Math.abs(roundTripAngles.tiltDeg - angles.tiltDeg)).toBeLessThan(1e-6);
    }
  });

  it('wrapDeg correctly maps to (-180, 180]', () => {
    expect(wrapDeg(0)).toBe(0);
    expect(wrapDeg(180)).toBe(180);
    expect(wrapDeg(-180)).toBe(180);
    expect(wrapDeg(181)).toBe(-179);
    expect(wrapDeg(-181)).toBe(179);
    expect(wrapDeg(540)).toBe(180);
  });

  it('angularDiffDeg computes shortest signed difference', () => {
    expect(angularDiffDeg(10, 5)).toBe(5);
    expect(angularDiffDeg(5, 10)).toBe(-5);
    expect(angularDiffDeg(-179, 179)).toBe(2);
    expect(angularDiffDeg(179, -179)).toBe(-2);
  });
});
