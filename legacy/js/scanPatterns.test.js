import { describe, it, expect } from 'vitest';
import { raster, spiral } from '../src/tracking/scanPatterns.js';
import { CAMERA_CONFIG, TRACKING_CONFIG, SLEW_PRESETS } from '../src/tracking/config.js';

describe('Scan Patterns (Sub-phase 2C)', () => {
  it('raster covers all pan/tilt cells within one full cycle and reports duration', () => {
    const r0 = raster(0, { activeSlewPreset: 'baseline' });
    const cycleDuration = r0.cycleDurationSec;

    console.log(`Reported raster full-cycle duration at baseline slew: ${cycleDuration.toFixed(2)} s`);
    expect(cycleDuration).toBeGreaterThan(0);

    const fov = CAMERA_CONFIG.fovDeg;
    const overlap = TRACKING_CONFIG.overlap;
    const cellPitch = fov * (1 - overlap); // 16 deg

    // Discretize coverage into pan/tilt bins
    const panBins = 12; // 30 deg each
    const tiltBins = 8; // ~14 deg each
    const visited = new Set();

    const sampleStepSec = 0.5;
    for (let t = 0; t <= cycleDuration; t += sampleStepSec) {
      const pt = raster(t, { activeSlewPreset: 'baseline' });
      // Map pan (-180, 180] to bin 0..11
      const pNorm = (pt.panDeg + 180) % 360;
      const pBin = Math.min(panBins - 1, Math.floor((pNorm / 360) * panBins));

      // Map tilt (-55, 55) to bin 0..7
      const tNorm = (pt.tiltDeg + 55) / 110;
      const tBin = Math.max(0, Math.min(tiltBins - 1, Math.floor(tNorm * tiltBins)));

      visited.add(`${pBin},${tBin}`);
    }

    const totalCells = panBins * tiltBins;
    const coverageFraction = visited.size / totalCells;

    // Assert high coverage across the entire field of regard
    expect(coverageFraction).toBeGreaterThan(0.9);
  });

  it('spiral expands out to reacquireMaxRadiusDeg and reports done', () => {
    const center = { panDeg: 45, tiltDeg: 10 };
    const maxRadius = TRACKING_CONFIG.reacquireMaxRadiusDeg;

    const s0 = spiral(0, center);
    expect(s0.radiusDeg).toBeCloseTo(0, 1);
    expect(s0.done).toBe(false);

    // Simulate spiral expansion over time
    let finalState = s0;
    for (let t = 1; t <= 60; t += 0.5) {
      const st = spiral(t, center);
      if (st.done) {
        finalState = st;
        break;
      }
      finalState = st;
    }

    expect(finalState.done).toBe(true);
    expect(finalState.radiusDeg).toBeGreaterThanOrEqual(maxRadius);
  });
});
