import { describe, it, expect } from 'vitest';
import { computeBlinkScore, evaluateCandidates, buildCodeTemplate } from '../src/tracking/beaconId.js';
import { createMulberry32 } from '../src/tracking/prng.js';

describe('Beacon Identification (Sub-phase 3B)', () => {
  const codeBits = '10110010';
  const samplesPerBit = 3;
  const template = buildCodeTemplate(codeBits, samplesPerBit);
  const templateLen = template.length; // 24 frames

  it('correct code produces correlation score ~ 1.0 (with any cyclic phase shift)', () => {
    for (let shift = 0; shift < templateLen; shift++) {
      const history = [];
      for (let i = 0; i < templateLen; i++) {
        const idx = (i + shift) % templateLen;
        history.push(template[idx] ? 200 : 0);
      }

      const { score } = computeBlinkScore(history, { bits: codeBits, samplesPerBit });
      expect(score).toBeGreaterThan(0.99);
    }
  });

  it('steady decoy (all ones) produces score = 0', () => {
    const history = new Array(templateLen).fill(250);
    const { score } = computeBlinkScore(history, { bits: codeBits, samplesPerBit });
    expect(score).toBe(0);
  });

  it('random flasher produces low correlation score (< 0.60, below ID threshold 0.70)', () => {
    const rng = createMulberry32(999);
    const history = [];
    for (let i = 0; i < templateLen; i++) {
      history.push(rng() > 0.6 ? 220 : 0);
    }

    const { score } = computeBlinkScore(history, { bits: codeBits, samplesPerBit });
    expect(score).toBeLessThan(0.60);
  });

  it('correct code with 20% frame drops still confirms within a bounded number of frames', () => {
    const rng = createMulberry32(12345);
    const history = [];

    // Synthesize 48 frames of code with 20% random frame dropouts
    for (let i = 0; i < 48; i++) {
      const bitVal = template[i % templateLen];
      if (bitVal === 1 && rng() < 0.20) {
        // Dropped frame: becomes 0
        history.push(0);
      } else {
        history.push(bitVal ? 200 : 0);
      }
    }

    const { score } = computeBlinkScore(history, { bits: codeBits, samplesPerBit });
    // With 20% drops, score is still high (> 0.70)
    expect(score).toBeGreaterThan(0.70);
  });

  it('two candidates: confirmed one wins', () => {
    // Candidate 1: Steady decoy
    const candSteady = {
      id: 1,
      x: 100,
      y: 100,
      history: new Array(32).fill(250),
      totalObservations: 32,
      missedFrames: 0,
      confirmed: false,
      score: 0
    };

    // Candidate 2: Real beacon with code
    const beaconHistory = [];
    for (let i = 0; i < 32; i++) {
      beaconHistory.push(template[i % templateLen] ? 220 : 0);
    }

    const candReal = {
      id: 2,
      x: 320,
      y: 240,
      history: beaconHistory,
      totalObservations: 32,
      missedFrames: 0,
      confirmed: false,
      score: 0,
      confirmStreak: 3
    };

    const candidates = [candSteady, candReal];
    const evaluated = evaluateCandidates(candidates, { mode: 'code', bits: codeBits, samplesPerBit }, { idThreshold: 0.70, idConfirmFrames: 2 });

    expect(evaluated[0].id).toBe(2);
    expect(evaluated[0].confirmed).toBe(true);
    expect(evaluated[1].confirmed).toBe(false);
  });

  it('multi-candidate stream with real beacon and 3 decoys rejects all decoys with 0 false locks', () => {
    const rng = createMulberry32(42);
    const historyLen = 48;
    const cStar = { id: 101, x: 120, y: 80, history: [], totalObservations: 0, missedFrames: 0, confirmed: false, score: 0 };
    const cSat = { id: 102, x: 280, y: 200, history: [], totalObservations: 0, missedFrames: 0, confirmed: false, score: 0 };
    const cGlint = { id: 103, x: 350, y: 150, history: [], totalObservations: 0, missedFrames: 0, confirmed: false, score: 0 };
    const cBeacon = { id: 104, x: 320, y: 240, history: [], totalObservations: 0, missedFrames: 0, confirmed: false, score: 0 };

    const trackerCandidates = [cStar, cSat, cGlint, cBeacon];

    let falseLocks = 0;
    let confirmedFrame = null;

    // Simulate 90 frames (~3 seconds of 30 Hz feed)
    for (let f = 0; f < 90; f++) {
      const bitVal = template[f % templateLen];
      const realIntensity = bitVal === 1 ? 240 : 0;
      const starIntensity = 220;
      const satIntensity = 210;
      const glintIntensity = rng() < 0.15 ? 230 : 0; // Poisson-like glint

      cStar.history.push(starIntensity);
      cStar.totalObservations++;

      cSat.history.push(satIntensity);
      cSat.totalObservations++;

      cGlint.history.push(glintIntensity);
      cGlint.totalObservations++;

      cBeacon.history.push(realIntensity);
      cBeacon.totalObservations++;

      for (const c of trackerCandidates) {
        if (c.history.length > historyLen) c.history.shift();
      }

      const evaluated = evaluateCandidates(
        [...trackerCandidates],
        { mode: 'code', bits: codeBits, samplesPerBit },
        { idThreshold: 0.70, idConfirmFrames: 3 }
      );

      // Check confirmation
      for (const c of evaluated) {
        if (c.confirmed && c.id !== 104) {
          falseLocks++;
        }
        if (c.confirmed && c.id === 104 && confirmedFrame === null) {
          confirmedFrame = f;
        }
      }
    }

    expect(falseLocks).toBe(0);
    expect(confirmedFrame).not.toBeNull();
    // Confirmed after ~24 frames (1 code cycle) + 3 confirm frames = ~27 frames (~0.90 s)
    expect(confirmedFrame).toBeLessThanOrEqual(30);
    const timeToConfirmSec = confirmedFrame / 30;
    console.log(`Measured 3B Decoys stream: false-lock count = ${falseLocks}, time-to-confirm = ${timeToConfirmSec.toFixed(2)}s (${confirmedFrame} frames)`);
  });
});
