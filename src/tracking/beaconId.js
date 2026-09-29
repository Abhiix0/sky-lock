import { BEACON_CODE, ID_CONFIG } from './config.js';

/**
 * Builds the oversampled discrete template vector for a given bit string and samples per bit.
 *
 * @param {string} bits - Binary string (e.g. '10110010')
 * @param {number} [samplesPerBit=3] - Samples per bit (default 3 at 30 Hz feed and 100 ms bit period)
 * @returns {Float32Array} Binary template array
 */
export function buildCodeTemplate(bits = '10110010', samplesPerBit = 3) {
  const template = new Float32Array(bits.length * samplesPerBit);
  for (let b = 0; b < bits.length; b++) {
    const val = bits[b] === '1' ? 1.0 : 0.0;
    for (let s = 0; s < samplesPerBit; s++) {
      template[b * samplesPerBit + s] = val;
    }
  }
  return template;
}

/**
 * Computes matched-filter correlation score in [0, 1] of a candidate's intensity history
 * against the known beacon blink code across all possible cyclic phase shifts.
 *
 * @param {Array<number>} history - Array of observed intensities (0 = absent/off, >0 = detected)
 * @param {Object} [codeConfig={}] - Configuration with bits and bitPeriodSec
 * @returns {{ score: number, bestShift: number }}
 */
export function computeBlinkScore(history = [], codeConfig = {}) {
  const bits = codeConfig.bits || BEACON_CODE.bits || '10110010';
  const samplesPerBit = codeConfig.samplesPerBit || 3;
  const template = buildCodeTemplate(bits, samplesPerBit);
  const templateLen = template.length; // e.g. 24 frames for 8 bits * 3 samples

  if (!history || history.length < templateLen) {
    return { score: 0, bestShift: 0 };
  }

  // Extract the most recent templateLen samples from history
  const recent = history.slice(-templateLen);

  // Binary thresholding: values > 0 are 1.0, otherwise 0.0
  const bin = new Float32Array(templateLen);
  let onesCount = 0;
  for (let i = 0; i < templateLen; i++) {
    const val = recent[i] > 0 ? 1.0 : 0.0;
    bin[i] = val;
    if (val > 0) onesCount++;
  }

  // Degenerate cases: all off (0 ones) or all on (steady light)
  if (onesCount === 0 || onesCount === templateLen) {
    return { score: 0, bestShift: 0 };
  }

  // Compute template statistics
  let sumT = 0;
  for (let i = 0; i < templateLen; i++) sumT += template[i];
  const meanT = sumT / templateLen;

  let varT = 0;
  for (let i = 0; i < templateLen; i++) {
    const d = template[i] - meanT;
    varT += d * d;
  }

  // Compute signal statistics
  let sumS = 0;
  for (let i = 0; i < templateLen; i++) sumS += bin[i];
  const meanS = sumS / templateLen;

  let varS = 0;
  for (let i = 0; i < templateLen; i++) {
    const d = bin[i] - meanS;
    varS += d * d;
  }

  if (varS < 1e-6 || varT < 1e-6) {
    return { score: 0, bestShift: 0 };
  }

  const denom = Math.sqrt(varS * varT);

  // Matched-filter correlation across all cyclic shifts
  let maxScore = -1;
  let bestShift = 0;

  for (let shift = 0; shift < templateLen; shift++) {
    let crossSum = 0;
    for (let i = 0; i < templateLen; i++) {
      const shiftedIdx = (i + shift) % templateLen;
      crossSum += (bin[i] - meanS) * (template[shiftedIdx] - meanT);
    }

    const r = crossSum / denom;
    if (r > maxScore) {
      maxScore = r;
      bestShift = shift;
    }
  }

  return {
    score: Math.max(0, Math.min(1.0, maxScore)),
    bestShift
  };
}

/**
 * Evaluates candidate list with matched-filter correlation and updates confirmation status.
 *
 * @param {Array<Object>} candidates - List of candidate objects from candidateTracker
 * @param {Object} [codeConfig={}]
 * @param {Object} [idConfig={}]
 * @returns {Array<Object>} Evaluated candidates
 */
export function evaluateCandidates(candidates = [], codeConfig = {}, idConfig = {}) {
  const threshold = idConfig.idThreshold ?? ID_CONFIG.idThreshold ?? 0.7;
  const confirmFrames = idConfig.idConfirmFrames ?? ID_CONFIG.idConfirmFrames ?? 3;
  const mode = codeConfig.mode ?? BEACON_CODE.mode ?? 'steady';

  for (const c of candidates) {
    if (mode === 'steady') {
      // In steady mode, any persistent candidate with observations is confirmed
      c.score = 1.0;
      if (c.totalObservations >= confirmFrames) {
        c.confirmed = true;
      }
      continue;
    }

    // Code mode: evaluate blink correlation
    const { score } = computeBlinkScore(c.history, codeConfig);
    c.score = score;

    if (score >= threshold) {
      c.confirmStreak = (c.confirmStreak || 0) + 1;
      if (c.confirmStreak >= confirmFrames) {
        c.confirmed = true;
      }
    } else {
      c.confirmStreak = Math.max(0, (c.confirmStreak || 0) - 1);
      // Un-confirm if score drops persistently
      if (c.confirmStreak === 0 && c.missedFrames > 5) {
        c.confirmed = false;
      }
    }
  }

  // Sort: confirmed candidate first, then highest score
  candidates.sort((a, b) => {
    if (a.confirmed !== b.confirmed) {
      return a.confirmed ? -1 : 1;
    }
    return b.score - a.score;
  });

  return candidates;
}

/**
 * Returns the confirmed candidate, or null if none is confirmed yet.
 *
 * @param {Array<Object>} candidates
 * @returns {Object|null}
 */
export function getConfirmedCandidate(candidates = []) {
  if (!candidates || candidates.length === 0) return null;
  return candidates.find((c) => c.confirmed) || null;
}
