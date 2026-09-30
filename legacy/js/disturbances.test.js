import { describe, it, expect, beforeEach } from 'vitest';
import { createDisturbanceManager, applySeparableBoxBlur } from '../src/tracking/disturbances.js';
import { DISTURBANCE_PRESETS } from '../src/tracking/config.js';

describe('Disturbances Module', () => {
  let mgr;

  beforeEach(() => {
    mgr = createDisturbanceManager({ seed: 42, preset: 'OFF' });
  });

  it('same seed produces identical sequences', () => {
    const mgr1 = createDisturbanceManager({ seed: 12345, preset: 'MED' });
    const mgr2 = createDisturbanceManager({ seed: 12345, preset: 'MED' });

    const seq1 = [];
    const seq2 = [];

    for (let t = 0.1; t <= 2.0; t += 0.1) {
      const turb1 = mgr1.getTurbulence(t);
      const vib1 = mgr1.getVibration(t);
      const drop1 = mgr1.shouldDropFrame();

      const turb2 = mgr2.getTurbulence(t);
      const vib2 = mgr2.getVibration(t);
      const drop2 = mgr2.shouldDropFrame();

      seq1.push({ turb: turb1, vib: vib1, drop: drop1 });
      seq2.push({ turb: turb2, vib: vib2, drop: drop2 });
    }

    expect(seq1).toEqual(seq2);
  });

  it('different seed produces different sequences', () => {
    const mgr1 = createDisturbanceManager({ seed: 11111, preset: 'MED' });
    const mgr2 = createDisturbanceManager({ seed: 99999, preset: 'MED' });

    const turb1 = mgr1.getTurbulence(0.5);
    const turb2 = mgr2.getTurbulence(0.5);

    expect(turb1.wanderPx[0]).not.toEqual(turb2.wanderPx[0]);
    expect(turb1.wanderPx[1]).not.toEqual(turb2.wanderPx[1]);

    const vib1 = mgr1.getVibration(0.5);
    const vib2 = mgr2.getVibration(0.5);
    expect(vib1.panJitterDeg).not.toEqual(vib2.panJitterDeg);
  });

  it('Off preset leaves a frame byte-identical', () => {
    mgr.setPreset('OFF');

    const width = 640;
    const height = 480;
    const data = new Uint8Array(width * height * 4);
    for (let i = 0; i < data.length; i++) {
      data[i] = (i * 37) & 0xff;
    }

    const originalCopy = new Uint8Array(data);

    const frame = {
      width,
      height,
      data,
      timestamp: 1.0,
      frameId: 10
    };

    mgr.applySensorStage(frame);

    // Assert every byte is exactly identical
    let dataMatches = true;
    for (let i = 0; i < data.length; i++) {
      if (frame.data[i] !== originalCopy[i]) {
        dataMatches = false;
        break;
      }
    }
    expect(dataMatches).toBe(true);

    let rawMatches = true;
    for (let i = 0; i < data.length; i++) {
      if (frame.rawData[i] !== originalCopy[i]) {
        rawMatches = false;
        break;
      }
    }
    expect(rawMatches).toBe(true);
  });

  it('noise sigma measured on a flat frame matches setting within 10%', () => {
    const targetSigma = 15.0;
    mgr.setPreset('OFF');
    mgr.setParam('noiseSigma', targetSigma);
    mgr.setParam('hotPixelsCount', 0);
    mgr.setParam('blurRadiusPx', 0);

    const width = 320;
    const height = 240;
    const baseVal = 128;
    const totalPixels = width * height;
    const data = new Uint8Array(totalPixels * 4);
    data.fill(baseVal);

    const frame = {
      width,
      height,
      data,
      timestamp: 1.0,
      frameId: 1
    };

    mgr.applySensorStage(frame);

    // Compute sample standard deviation of red channel
    let sum = 0;
    let sumSq = 0;
    for (let i = 0; i < data.length; i += 4) {
      const v = data[i];
      sum += v;
      sumSq += v * v;
    }

    const mean = sum / totalPixels;
    const variance = (sumSq / totalPixels) - (mean * mean);
    const measuredSigma = Math.sqrt(Math.max(0, variance));

    // Standard deviation must match target within 10%
    const relativeError = Math.abs(measuredSigma - targetSigma) / targetSigma;
    expect(relativeError).toBeLessThan(0.10);
  });

  it('applies separable box blur correctly', () => {
    const w = 10;
    const h = 10;
    const data = new Uint8Array(w * h * 4);
    const scratch = new Uint8Array(w * h * 4);

    // Single impulse pixel at center (5, 5) with value 255
    const centerIdx = (5 * w + 5) * 4;
    data[centerIdx] = 255;

    applySeparableBoxBlur(data, w, h, 1, scratch);

    // After radius 1 box blur (3x3 kernel), center pixel value should be spread
    // 255 / (3 * 3) = 28.33 => 28
    expect(data[centerIdx]).toBeGreaterThan(20);
    expect(data[centerIdx]).toBeLessThan(35);

    // Adjacent pixels should have non-zero value
    const leftIdx = (5 * w + 4) * 4;
    expect(data[leftIdx]).toBeGreaterThan(20);
  });

  it('presets OFF, LOW, MED, HIGH configure parameters correctly', () => {
    mgr.setPreset('LOW');
    expect(mgr.getPreset()).toBe('LOW');
    expect(mgr.getParams().wanderRmsPx).toBe(DISTURBANCE_PRESETS.LOW.wanderRmsPx);
    expect(mgr.getParams().noiseSigma).toBe(DISTURBANCE_PRESETS.LOW.noiseSigma);

    mgr.setPreset('MED');
    expect(mgr.getPreset()).toBe('MED');
    expect(mgr.getParams().jitterRmsDeg).toBe(DISTURBANCE_PRESETS.MED.jitterRmsDeg);

    mgr.setPreset('HIGH');
    expect(mgr.getPreset()).toBe('HIGH');
    expect(mgr.getParams().blurRadiusPx).toBe(DISTURBANCE_PRESETS.HIGH.blurRadiusPx);

    mgr.setPreset('OFF');
    expect(mgr.getPreset()).toBe('OFF');
    expect(mgr.getParams().noiseSigma).toBe(0);
  });
});
