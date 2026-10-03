import { DISTURBANCE_PRESETS } from './config.js';
import { createMulberry32, createGaussian } from './prng.js';

/**
 * Fast 1D separable box blur on RGBA Uint8Array buffer in-place using a scratch buffer.
 *
 * @param {Uint8Array} data - RGBA buffer of length w * h * 4
 * @param {number} width - Frame width
 * @param {number} height - Frame height
 * @param {number} radius - Blur radius in pixels (1, 2, 3...)
 * @param {Uint8Array} scratch - Scratch buffer of length w * h * 4
 */
export function applySeparableBoxBlur(data, width, height, radius, scratch) {
  if (radius <= 0) return;
  const r = Math.floor(radius);
  const w = width;
  const h = height;
  const windowSize = 2 * r + 1;
  const invWindow = 1.0 / windowSize;

  // Pass 1: Horizontal blur from data -> scratch
  for (let y = 0; y < h; y++) {
    const rowOffset = y * w * 4;
    for (let x = 0; x < w; x++) {
      let sumR = 0;
      let sumG = 0;
      let sumB = 0;
      for (let i = -r; i <= r; i++) {
        const ix = Math.min(Math.max(x + i, 0), w - 1);
        const idx = rowOffset + ix * 4;
        sumR += data[idx];
        sumG += data[idx + 1];
        sumB += data[idx + 2];
      }
      const outIdx = rowOffset + x * 4;
      scratch[outIdx] = (sumR * invWindow) | 0;
      scratch[outIdx + 1] = (sumG * invWindow) | 0;
      scratch[outIdx + 2] = (sumB * invWindow) | 0;
      scratch[outIdx + 3] = data[outIdx + 3];
    }
  }

  // Pass 2: Vertical blur from scratch -> data
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      let sumR = 0;
      let sumG = 0;
      let sumB = 0;
      for (let j = -r; j <= r; j++) {
        const iy = Math.min(Math.max(y + j, 0), h - 1);
        const idx = (iy * w + x) * 4;
        sumR += scratch[idx];
        sumG += scratch[idx + 1];
        sumB += scratch[idx + 2];
      }
      const outIdx = (y * w + x) * 4;
      data[outIdx] = (sumR * invWindow) | 0;
      data[outIdx + 1] = (sumG * invWindow) | 0;
      data[outIdx + 2] = (sumB * invWindow) | 0;
    }
  }
}

/**
 * Creates a Disturbance Manager instance.
 *
 * @param {Object} [initialOptions={}]
 * @returns {Object} Disturbance manager instance
 */
export function createDisturbanceManager(initialOptions = {}) {
  let activeSeed = initialOptions.seed !== undefined ? initialOptions.seed : 12345;
  let activePreset = initialOptions.preset || 'OFF';

  // Current parameters (cloned from preset)
  let params = { ...DISTURBANCE_PRESETS[activePreset] };
  if (initialOptions.params) {
    params = { ...params, ...initialOptions.params };
  }

  // PRNG streams
  let turbRng;
  let turbGaussian;
  let vibRng;
  let vibGaussian;
  let sensRng;
  let sensGaussian;
  let dropRng;

  // Internal physical state variables (Ornstein-Uhlenbeck processes)
  let wanderX = 0;
  let wanderY = 0;
  let scintState = 0;
  let lastTurbTime = null;

  let jitterPan = 0;
  let jitterTilt = 0;
  let lastVibTime = null;

  let droppedFramesCount = 0;

  // Hot pixels cache: array of byte offsets in RGBA buffer
  let hotPixelOffsets = [];

  // Scratch buffers for zero-allocation sensor processing
  let rawCopyBuffer = null;
  let blurScratchBuffer = null;

  /**
   * Reinitialize PRNG streams and internal dynamic states with the given seed.
   *
   * @param {number} seed
   */
  function setSeed(seed) {
    activeSeed = seed >>> 0 || 12345;

    // Derive deterministic stream seeds using large coprimes
    const sTurb = (activeSeed ^ 0x9e3779b9) >>> 0;
    const sVib = (activeSeed ^ 0x6a09e667) >>> 0;
    const sSens = (activeSeed ^ 0xbb67ae85) >>> 0;
    const sDrop = (activeSeed ^ 0x3c6ef372) >>> 0;

    turbRng = createMulberry32(sTurb);
    turbGaussian = createGaussian(turbRng);

    vibRng = createMulberry32(sVib);
    vibGaussian = createGaussian(vibRng);

    sensRng = createMulberry32(sSens);
    sensGaussian = createGaussian(sensRng);

    dropRng = createMulberry32(sDrop);

    // Reset OU process states
    wanderX = 0;
    wanderY = 0;
    scintState = 0;
    lastTurbTime = null;

    jitterPan = 0;
    jitterTilt = 0;
    lastVibTime = null;

    droppedFramesCount = 0;

    // Regenerate hot pixel locations (for 640x480 standard resolution)
    regenerateHotPixels(640, 480);
  }

  /**
   * Regenerate cached hot pixel offsets in the sensor buffer.
   *
   * @param {number} w - Frame width
   * @param {number} h - Frame height
   */
  function regenerateHotPixels(w, h) {
    hotPixelOffsets = [];
    const count = params.hotPixelsCount || 0;
    if (count <= 0) return;

    const totalPixels = w * h;
    for (let i = 0; i < count; i++) {
      const pxIdx = Math.floor(sensRng() * totalPixels);
      hotPixelOffsets.push(pxIdx * 4);
    }
  }

  // Initialize streams
  setSeed(activeSeed);

  /**
   * Set disturbance preset by name (OFF | LOW | MED | HIGH).
   *
   * @param {'OFF'|'LOW'|'MED'|'HIGH'|'Off'|'Low'|'Med'|'High'} name
   */
  function setPreset(name) {
    const upper = String(name).toUpperCase();
    if (!DISTURBANCE_PRESETS[upper]) {
      console.warn(`[Disturbances] Unknown preset: ${name}, defaulting to OFF`);
      activePreset = 'OFF';
    } else {
      activePreset = upper;
    }
    params = { ...DISTURBANCE_PRESETS[activePreset] };
    regenerateHotPixels(640, 480);
  }

  /**
   * Set individual parameter value (marks preset as CUSTOM).
   *
   * @param {string} key
   * @param {number} val
   */
  function setParam(key, val) {
    if (Object.prototype.hasOwnProperty.call(params, key)) {
      params[key] = val;
      activePreset = 'CUSTOM';
      if (key === 'hotPixelsCount') {
        regenerateHotPixels(640, 480);
      }
    }
  }

  /**
   * Step atmospheric turbulence OU processes and log-normal scintillation.
   *
   * @param {number} simTimeSec - Current simulation time
   * @returns {{ wanderPx: [number, number], scintillation: number }}
   */
  function getTurbulence(simTimeSec) {
    if (params.wanderRmsPx === 0 && params.scintillationSigma === 0) {
      wanderX = 0;
      wanderY = 0;
      scintState = 0;
      lastTurbTime = simTimeSec;
      return { wanderPx: [0, 0], scintillation: 1.0 };
    }

    if (lastTurbTime === null) {
      lastTurbTime = simTimeSec;
      wanderX = turbGaussian(0, params.wanderRmsPx);
      wanderY = turbGaussian(0, params.wanderRmsPx);
      scintState = turbGaussian(0, params.scintillationSigma);
    } else {
      const dt = Math.max(0, simTimeSec - lastTurbTime);
      lastTurbTime = simTimeSec;

      if (dt > 0) {
        // Ornstein-Uhlenbeck continuous decay factor: alpha = exp(-2*pi*fc*dt)
        const omegaWander = 2.0 * Math.PI * (params.wanderCornerHz || 2.0);
        const alphaW = Math.exp(-omegaWander * dt);
        const sigmaW = params.wanderRmsPx * Math.sqrt(Math.max(0, 1 - alphaW * alphaW));

        wanderX = alphaW * wanderX + turbGaussian(0, sigmaW);
        wanderY = alphaW * wanderY + turbGaussian(0, sigmaW);

        // Smooth correlated log-normal scintillation
        const omegaScint = 2.0 * Math.PI * 4.0;
        const alphaS = Math.exp(-omegaScint * dt);
        const sigmaS = params.scintillationSigma * Math.sqrt(Math.max(0, 1 - alphaS * alphaS));
        scintState = alphaS * scintState + turbGaussian(0, sigmaS);
      }
    }

    // Scintillation multiplier: I = exp(-0.5*sigma^2 + chi), so E[I] = 1.0
    const meanCorrection = -0.5 * params.scintillationSigma * params.scintillationSigma;
    const scintillation = Math.max(0.01, Math.min(4.0, Math.exp(meanCorrection + scintState)));

    return {
      wanderPx: [wanderX, wanderY],
      scintillation
    };
  }

  /**
   * Step platform vibration angular jitter (band-limited noise at vibrationHz).
   *
   * @param {number} simTimeSec - Current simulation time
   * @returns {{ panJitterDeg: number, tiltJitterDeg: number }}
   */
  function getVibration(simTimeSec) {
    if (params.jitterRmsDeg === 0) {
      jitterPan = 0;
      jitterTilt = 0;
      lastVibTime = simTimeSec;
      return { panJitterDeg: 0, tiltJitterDeg: 0 };
    }

    if (lastVibTime === null) {
      lastVibTime = simTimeSec;
      jitterPan = vibGaussian(0, params.jitterRmsDeg);
      jitterTilt = vibGaussian(0, params.jitterRmsDeg);
    } else {
      const dt = Math.max(0, simTimeSec - lastVibTime);
      lastVibTime = simTimeSec;

      if (dt > 0) {
        const omegaVib = 2.0 * Math.PI * (params.vibrationHz || 10.0);
        const alphaV = Math.exp(-omegaVib * dt);
        const sigmaV = params.jitterRmsDeg * Math.sqrt(Math.max(0, 1 - alphaV * alphaV));

        jitterPan = alphaV * jitterPan + vibGaussian(0, sigmaV);
        jitterTilt = alphaV * jitterTilt + vibGaussian(0, sigmaV);
      }
    }

    return {
      panJitterDeg: jitterPan,
      tiltJitterDeg: jitterTilt
    };
  }

  /**
   * Check if the current feed frame should be dropped.
   * Increments droppedFramesCount if true.
   *
   * @returns {boolean}
   */
  function shouldDropFrame() {
    if (!params.dropProbability || params.dropProbability <= 0) return false;
    const dropped = dropRng() < params.dropProbability;
    if (dropped) {
      droppedFramesCount++;
    }
    return dropped;
  }

  /**
   * Apply sensor noise, hot pixels, and blur stage to a camera feed frame.
   * Preserves raw pixels in frame.rawData for ground-truth debugging.
   * Modifies frame.data in-place so that detector and PiP see the post-disturbance frame.
   *
   * @param {Object} frame - Camera frame payload { width, height, data, timestamp, frameId }
   * @returns {Object} frame
   */
  function applySensorStage(frame) {
    if (!frame || !frame.data || frame.data.length === 0) return frame;

    const len = frame.data.length;

    // 1. Preserve untouched raw frame buffer
    if (!rawCopyBuffer || rawCopyBuffer.length !== len) {
      rawCopyBuffer = new Uint8Array(len);
    }
    rawCopyBuffer.set(frame.data);
    frame.rawData = rawCopyBuffer;

    // Check if sensor effects are active
    const hasNoise = params.noiseSigma > 0;
    const hasHot = params.hotPixelsCount > 0 && hotPixelOffsets.length > 0;
    const hasBlur = params.blurRadiusPx > 0;

    if (!hasNoise && !hasHot && !hasBlur) {
      // Off preset: completely byte-identical
      return frame;
    }

    const data = frame.data;
    const sigma = params.noiseSigma;

    // 2. Gaussian read noise on RGB channels
    if (hasNoise) {
      for (let i = 0; i < len; i += 4) {
        const nr = sensGaussian(0, sigma);
        const ng = sensGaussian(0, sigma);
        const nb = sensGaussian(0, sigma);

        data[i] = Math.min(255, Math.max(0, (data[i] + nr + 0.5) | 0));
        data[i + 1] = Math.min(255, Math.max(0, (data[i + 1] + ng + 0.5) | 0));
        data[i + 2] = Math.min(255, Math.max(0, (data[i + 2] + nb + 0.5) | 0));
      }
    }

    // 3. Hot pixels
    if (hasHot) {
      for (let k = 0; k < hotPixelOffsets.length; k++) {
        const off = hotPixelOffsets[k];
        if (off < len - 3) {
          data[off] = 255;
          data[off + 1] = 255;
          data[off + 2] = 255;
        }
      }
    }

    // 4. Separable blur
    if (hasBlur) {
      if (!blurScratchBuffer || blurScratchBuffer.length !== len) {
        blurScratchBuffer = new Uint8Array(len);
      }
      applySeparableBoxBlur(
        data,
        frame.width,
        frame.height,
        params.blurRadiusPx,
        blurScratchBuffer
      );
    }

    return frame;
  }

  return {
    setSeed,
    getSeed: () => activeSeed,
    setPreset,
    getPreset: () => activePreset,
    setParam,
    getParams: () => ({ ...params }),
    getTurbulence,
    getVibration,
    shouldDropFrame,
    getDroppedFramesCount: () => droppedFramesCount,
    applySensorStage,
    reset: () => setSeed(activeSeed)
  };
}

/**
 * Singleton instance shared across the application.
 */
export const disturbances = createDisturbanceManager();
