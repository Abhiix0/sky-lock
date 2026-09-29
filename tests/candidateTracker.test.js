import { describe, it, expect } from 'vitest';
import { createCandidateTracker } from '../src/tracking/candidateTracker.js';

describe('Candidate Tracker (Sub-phase 3B)', () => {
  it('instantiates and tracks candidates across consecutive frames', () => {
    const tracker = createCandidateTracker({ historyWindowFrames: 16 });

    // Frame 1: blob at (200, 150)
    let cands = tracker.update([{ cx: 200, cy: 150, peak: 240, snr: 20 }], 0.0);
    expect(cands.length).toBe(1);
    expect(cands[0].x).toBe(200);
    expect(cands[0].y).toBe(150);
    expect(cands[0].history).toEqual([240]);

    // Frame 2: blob moved slightly to (202, 151)
    cands = tracker.update([{ cx: 202, cy: 151, peak: 245, snr: 21 }], 0.033);
    expect(cands.length).toBe(1);
    expect(cands[0].x).toBe(202);
    expect(cands[0].y).toBe(151);
    expect(cands[0].history).toEqual([240, 245]);
  });

  it('tracks multiple simultaneous candidates with nearest-neighbor association', () => {
    const tracker = createCandidateTracker();

    // Frame 1: two distinct blobs
    tracker.update([
      { cx: 100, cy: 100, peak: 200 },
      { cx: 400, cy: 300, peak: 220 }
    ], 0.0);

    let cands = tracker.getCandidates();
    expect(cands.length).toBe(2);

    // Frame 2: both blobs updated
    tracker.update([
      { cx: 101, cy: 101, peak: 205 },
      { cx: 398, cy: 302, peak: 218 }
    ], 0.033);

    cands = tracker.getCandidates();
    expect(cands.length).toBe(2);
    const cand1 = cands.find((c) => Math.hypot(c.x - 101, c.y - 101) < 2);
    const cand2 = cands.find((c) => Math.hypot(c.x - 398, c.y - 302) < 2);

    expect(cand1).toBeDefined();
    expect(cand2).toBeDefined();
    expect(cand1.history.length).toBe(2);
    expect(cand2.history.length).toBe(2);
  });

  it('appends zero on missed frame and prunes dead candidates after maxMissFrames', () => {
    const tracker = createCandidateTracker({ maxMissFrames: 5 });

    tracker.update([{ cx: 200, cy: 200, peak: 250 }], 0.0);
    expect(tracker.getCandidates().length).toBe(1);

    // Frame with no detection: missed frame
    tracker.update([], 0.033);
    let cands = tracker.getCandidates();
    expect(cands.length).toBe(1);
    expect(cands[0].missedFrames).toBe(1);
    expect(cands[0].history).toEqual([250, 0]);

    // 5 more empty frames -> exceeds maxMissFrames (5)
    for (let i = 0; i < 5; i++) {
      tracker.update([], 0.066 + i * 0.033);
    }

    cands = tracker.getCandidates();
    expect(cands.length).toBe(0);
  });
});
