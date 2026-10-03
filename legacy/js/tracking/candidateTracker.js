import { ID_CONFIG } from './config.js';

/**
 * Multi-Candidate Tracker with Nearest-Neighbor Data Association.
 * Maintains rolling intensity history per candidate for matched-filter blink code correlation.
 *
 * @param {Object} [config={}]
 * @returns {Object} Candidate tracker instance
 */
export function createCandidateTracker(config = {}) {
  const maxHistoryLength = config.historyWindowFrames || ID_CONFIG.historyWindowFrames || 32;
  const associationGatePx = config.associationGatePx || 25;
  const maxMissFrames = config.maxMissFrames || 18;

  let candidates = [];
  let nextCandidateId = 1;

  /**
   * Update candidates with detections from the current feed frame.
   *
   * @param {Array<Object>} detections - Blobs detected in current frame [{ cx, cy, peak, area, snr }, ...]
   * @param {number} simTime - Simulation time in seconds
   * @param {Object} [predictedPos] - Optional Kalman predicted pixel { x, y }
   * @returns {Array<Object>} Updated candidates list
   */
  function update(detections = [], simTime = 0, predictedPos = null) {
    const matchedDetectionIndices = new Set();
    const matchedCandidateIds = new Set();

    // 1. Data Association (Nearest-Neighbor)
    for (const candidate of candidates) {
      let bestDist = Infinity;
      let bestDetIdx = -1;

      // Expand gate if candidate has missed frames
      const gate =
        candidate.confirmed && predictedPos
          ? associationGatePx * 1.5
          : associationGatePx + candidate.missedFrames * 2.0;

      for (let i = 0; i < detections.length; i++) {
        if (matchedDetectionIndices.has(i)) continue;
        const d = detections[i];
        const dist = Math.hypot(d.cx - candidate.x, d.cy - candidate.y);

        if (dist <= gate && dist < bestDist) {
          bestDist = dist;
          bestDetIdx = i;
        }
      }

      if (bestDetIdx !== -1) {
        // Associated!
        const d = detections[bestDetIdx];
        candidate.x = d.cx;
        candidate.y = d.cy;
        candidate.lastDetection = d;
        candidate.missedFrames = 0;
        candidate.totalObservations++;
        candidate.lastSeenTime = simTime;

        // Push normalized intensity (relative to baseline detection threshold)
        const intensity = d.peak > 0 ? d.peak : 1.0;
        candidate.history.push(intensity);
        if (candidate.history.length > maxHistoryLength) {
          candidate.history.shift();
        }

        matchedDetectionIndices.add(bestDetIdx);
        matchedCandidateIds.add(candidate.id);
      } else {
        // Missed this frame
        candidate.missedFrames++;
        candidate.history.push(0);
        if (candidate.history.length > maxHistoryLength) {
          candidate.history.shift();
        }
      }
    }

    // 2. Instantiate new candidates for unmatched detections
    for (let i = 0; i < detections.length; i++) {
      if (matchedDetectionIndices.has(i)) continue;
      const d = detections[i];

      const newCand = {
        id: nextCandidateId++,
        x: d.cx,
        y: d.cy,
        lastDetection: d,
        missedFrames: 0,
        totalObservations: 1,
        lastSeenTime: simTime,
        history: [d.peak > 0 ? d.peak : 1.0],
        score: 0,
        confirmed: false,
        confirmStreak: 0
      };

      candidates.push(newCand);
    }

    // 3. Prune dead candidates
    candidates = candidates.filter((c) => {
      // Allow confirmed candidate more misses to survive short dropouts
      const allowedMisses = c.confirmed ? maxMissFrames * 2 : maxMissFrames;
      return c.missedFrames <= allowedMisses;
    });

    return candidates;
  }

  /**
   * Reset candidate tracker.
   */
  function reset() {
    candidates = [];
    nextCandidateId = 1;
  }

  return {
    update,
    reset,
    getCandidates: () => candidates
  };
}
