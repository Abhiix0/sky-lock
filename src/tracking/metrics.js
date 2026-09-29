import { CAMERA_CONFIG } from './config.js';

/**
 * Creates the performance metrics tracking engine.
 * Computes acquisition, reacquisition, pointing error, lock retention,
 * computational latency, and false-lock metrics according to docs/METRICS.md.
 *
 * @param {Object} [options={}]
 * @param {Object} [options.cameraConfig=CAMERA_CONFIG]
 * @param {number} [options.lockRadiusPx=30]
 * @param {number} [options.falseLockPx=50]
 * @returns {Object} Metrics module instance
 */
export function createMetrics(options = {}) {
  const camCfg = options.cameraConfig || CAMERA_CONFIG;
  const lockRadiusPx = options.lockRadiusPx ?? 30;
  const falseLockPx = options.falseLockPx ?? 50;

  const width = camCfg.feedWidth || camCfg.width || 640;
  const height = camCfg.feedHeight || camCfg.height || 480;
  const fovDeg = camCfg.fovDeg || 20;

  // Milliradians per pixel conversion factor
  // mrad = px * (fovRad / heightPx) * 1000
  const fovRad = (fovDeg * Math.PI) / 180;
  const mradPerPx = (fovRad / height) * 1000;
  const imgCx = width / 2;
  const imgCy = height / 2;

  // State accumulation variables
  let samples = [];
  let events = [];

  let firstObservableTime = null;
  let firstTrackTime = null;
  let hasTrackedOnce = false;

  let currentlyObservable = false;
  let _currentOcclusionStart = null;
  let lastEmergeTime = null;
  let waitingForReacq = false;
  let reacquisitionList = [];

  let falseLockSpans = 0;
  let currentFalseLockStartTime = null;
  let hasCountedCurrentFalseLock = false;

  let totalSimTime = 0;
  let observableTime = 0;
  let inTrackTime = 0;
  let inLockRadiusTime = 0;

  let lastSimTime = null;

  function reset() {
    samples = [];
    events = [];
    firstObservableTime = null;
    firstTrackTime = null;
    hasTrackedOnce = false;
    currentlyObservable = false;
    _currentOcclusionStart = null;
    lastEmergeTime = null;
    waitingForReacq = false;
    reacquisitionList = [];
    falseLockSpans = 0;
    currentFalseLockStartTime = null;
    hasCountedCurrentFalseLock = false;
    totalSimTime = 0;
    observableTime = 0;
    inTrackTime = 0;
    inLockRadiusTime = 0;
    lastSimTime = null;
  }

  /**
   * Consume a frame sample.
   *
   * @param {Object} sample
   * @param {number} sample.simTime - Simulation timestamp in seconds
   * @param {string} sample.state - Active tracker state ('SEARCH'|'ACQUIRE'|'TRACK'|'LOST'|'REACQUIRE')
   * @param {Object} sample.groundTruth - Ground truth telemetry {pixelX, pixelY, inFrustum, losClear, reachable}
   * @param {Object} [sample.estimatePx] - Kalman estimate projected pixel {x, y}
   * @param {Object} [sample.detectionPx] - Centroid of detected blob {x, y}
   * @param {number} [sample.procMs=0] - Frame processing latency in ms
   * @param {number} [sample.fps=60] - Instantaneous render FPS
   * @param {number|null} [sample.confirmedId=null] - Confirmed candidate ID
   * @param {number} [sample.droppedFrames=0] - Dropped frames count
   */
  function addSample(sample) {
    if (!sample) return;
    const t = sample.simTime;
    const dt = lastSimTime !== null ? Math.max(0, t - lastSimTime) : 0;
    lastSimTime = t;

    totalSimTime += dt;

    const gt = sample.groundTruth || {};
    const losClear = gt.losClear !== undefined ? !!gt.losClear : true;
    const reachable = gt.reachable !== undefined ? !!gt.reachable : true;
    const isObs = losClear && reachable;

    // Track first observable timestamp
    if (isObs && firstObservableTime === null) {
      firstObservableTime = t;
    }

    if (isObs) {
      observableTime += dt;
    }

    // Detect occlusion transition: observable -> unobservable
    if (currentlyObservable && !isObs) {
      _currentOcclusionStart = t;
      if (hasTrackedOnce) {
        waitingForReacq = true;
      }
    }
    // Detect emergence: unobservable -> observable
    else if (!currentlyObservable && isObs) {
      if (waitingForReacq) {
        lastEmergeTime = t;
      }
    }
    currentlyObservable = isObs;

    // Track state transitions & timing
    const state = sample.state;
    if (state === 'TRACK') {
      if (!hasTrackedOnce) {
        hasTrackedOnce = true;
        firstTrackTime = t;
      }

      if (waitingForReacq && lastEmergeTime !== null) {
        const dtReacq = t - lastEmergeTime;
        reacquisitionList.push(dtReacq);
        waitingForReacq = false;
        lastEmergeTime = null;
      }

      inTrackTime += dt;
    }

    // Compute Pointing Error & Tracking Error
    let pointingErrPx = null;
    let trackingErrPx = null;

    if (gt.pixelX !== undefined && gt.pixelY !== undefined) {
      // Pointing error: distance from image center (cx, cy) to ground-truth pixel
      pointingErrPx = Math.hypot(gt.pixelX - imgCx, gt.pixelY - imgCy);

      if (sample.estimatePx) {
        // Tracking error: distance from Kalman estimate pixel to ground-truth pixel
        trackingErrPx = Math.hypot(gt.pixelX - sample.estimatePx.x, gt.pixelY - sample.estimatePx.y);
      }
    }

    // Lock retention condition: in TRACK, observable, and pointing error < lockRadiusPx
    if (state === 'TRACK' && isObs && pointingErrPx !== null && pointingErrPx < lockRadiusPx) {
      inLockRadiusTime += dt;
    }

    // False lock detection: in TRACK for > 1.0 s while error > falseLockPx
    if (state === 'TRACK' && isObs && pointingErrPx !== null && pointingErrPx > falseLockPx) {
      if (currentFalseLockStartTime === null) {
        currentFalseLockStartTime = t;
      } else if (!hasCountedCurrentFalseLock && (t - currentFalseLockStartTime >= 1.0)) {
        falseLockSpans++;
        hasCountedCurrentFalseLock = true;
      }
    } else {
      currentFalseLockStartTime = null;
      hasCountedCurrentFalseLock = false;
    }

    const record = {
      simTime: t,
      state,
      isObservable: isObs,
      pointingErrPx: isObs && state === 'TRACK' ? pointingErrPx : null,
      trackingErrPx: isObs && state === 'TRACK' ? trackingErrPx : null,
      pointingErrMrad: isObs && state === 'TRACK' && pointingErrPx !== null ? pointingErrPx * mradPerPx : null,
      trackingErrMrad: isObs && state === 'TRACK' && trackingErrPx !== null ? trackingErrPx * mradPerPx : null,
      procMs: sample.procMs || 0,
      fps: sample.fps || 60,
      confirmedId: sample.confirmedId || null,
      droppedFrames: sample.droppedFrames || 0
    };

    samples.push(record);
  }

  function onStateChange(event) {
    events.push(event);
  }

  /**
   * Helper to compute mean, RMS, max, and p95 of an array of numbers.
   *
   * @param {Array<number>} arr
   * @returns {{ mean: number, rms: number, max: number, p95: number }}
   */
  function computeDistribution(arr) {
    if (!arr || arr.length === 0) {
      return { mean: 0, rms: 0, max: 0, p95: 0 };
    }
    let sum = 0;
    let sumSq = 0;
    let max = -Infinity;
    for (let i = 0; i < arr.length; i++) {
      const v = arr[i];
      sum += v;
      sumSq += v * v;
      if (v > max) max = v;
    }
    const mean = sum / arr.length;
    const rms = Math.sqrt(sumSq / arr.length);

    // Compute p95
    const sorted = arr.slice().sort((a, b) => a - b);
    const p95Idx = Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95));
    const p95 = sorted[p95Idx];

    return { mean, rms, max, p95 };
  }

  /**
   * Get full summary statistics.
   *
   * @returns {Object}
   */
  function getSummary() {
    const ptErrorsPx = [];
    const ptErrorsMrad = [];
    const trErrorsPx = [];
    const trErrorsMrad = [];
    const procLatencies = [];
    const fpsValues = [];
    let lastDropped = 0;

    for (let i = 0; i < samples.length; i++) {
      const s = samples[i];
      if (s.pointingErrPx !== null) ptErrorsPx.push(s.pointingErrPx);
      if (s.pointingErrMrad !== null) ptErrorsMrad.push(s.pointingErrMrad);
      if (s.trackingErrPx !== null) trErrorsPx.push(s.trackingErrPx);
      if (s.trackingErrMrad !== null) trErrorsMrad.push(s.trackingErrMrad);
      if (s.procMs > 0) procLatencies.push(s.procMs);
      if (s.fps > 0) fpsValues.push(s.fps);
      if (s.droppedFrames > lastDropped) lastDropped = s.droppedFrames;
    }

    const ptDistPx = computeDistribution(ptErrorsPx);
    const ptDistMrad = computeDistribution(ptErrorsMrad);
    const trDistPx = computeDistribution(trErrorsPx);
    const trDistMrad = computeDistribution(trErrorsMrad);
    const procDist = computeDistribution(procLatencies);

    let minFps = 60;
    let sumFps = 0;
    for (let i = 0; i < fpsValues.length; i++) {
      const f = fpsValues[i];
      sumFps += f;
      if (f < minFps) minFps = f;
    }
    const meanFps = fpsValues.length > 0 ? sumFps / fpsValues.length : 60;

    const reacqSum = reacquisitionList.reduce((acc, v) => acc + v, 0);
    const reacqMean = reacquisitionList.length > 0 ? reacqSum / reacquisitionList.length : 0;
    const reacqMax = reacquisitionList.length > 0 ? Math.max(...reacquisitionList) : 0;

    const retention = observableTime > 0 ? (inLockRadiusTime / observableTime) * 100 : 0;

    const acqTime = (firstTrackTime !== null && firstObservableTime !== null)
      ? Math.max(0, firstTrackTime - firstObservableTime)
      : null;

    return {
      totalSimTimeSec: totalSimTime,
      observableTimeSec: observableTime,
      inTrackTimeSec: inTrackTime,
      inLockRadiusTimeSec: inLockRadiusTime,
      lockRetentionRate: retention, // in percent
      firstObservableTime,
      firstTrackTime,
      acquisitionTimeSec: acqTime,
      acquisitionFromStartSec: firstTrackTime,
      reacquisitions: reacquisitionList,
      reacquisitionMeanSec: reacqMean,
      reacquisitionMaxSec: reacqMax,
      pointingError: {
        meanPx: ptDistPx.mean,
        rmsPx: ptDistPx.rms,
        maxPx: ptDistPx.max,
        p95Px: ptDistPx.p95,
        meanMrad: ptDistMrad.mean,
        rmsMrad: ptDistMrad.rms,
        maxMrad: ptDistMrad.max,
        p95Mrad: ptDistMrad.p95
      },
      trackingError: {
        meanPx: trDistPx.mean,
        rmsPx: trDistPx.rms,
        maxPx: trDistPx.max,
        p95Px: trDistPx.p95,
        meanMrad: trDistMrad.mean,
        rmsMrad: trDistMrad.rms,
        maxMrad: trDistMrad.max,
        p95Mrad: trDistMrad.p95
      },
      falseLocks: falseLockSpans,
      processingMs: {
        mean: procDist.mean,
        p95: procDist.p95,
        max: procDist.max
      },
      fps: {
        mean: meanFps,
        min: minFps
      },
      droppedFrames: lastDropped
    };
  }

  /**
   * Return decimated time series for visualization in charts.
   *
   * @param {number} [maxPoints=300]
   * @returns {Array<Object>}
   */
  function getTimeSeries(maxPoints = 300) {
    if (samples.length <= maxPoints) {
      return samples.slice();
    }
    const step = Math.ceil(samples.length / maxPoints);
    const decimated = [];
    for (let i = 0; i < samples.length; i += step) {
      decimated.push(samples[i]);
    }
    return decimated;
  }

  /**
   * Export all rows for benchmark or CSV output.
   *
   * @returns {Array<Object>}
   */
  function exportRows() {
    return samples.map((s) => ({
      simTime: s.simTime.toFixed(3),
      state: s.state,
      isObservable: s.isObservable ? 1 : 0,
      pointingErrPx: s.pointingErrPx !== null ? s.pointingErrPx.toFixed(2) : '',
      trackingErrPx: s.trackingErrPx !== null ? s.trackingErrPx.toFixed(2) : '',
      pointingErrMrad: s.pointingErrMrad !== null ? s.pointingErrMrad.toFixed(3) : '',
      trackingErrMrad: s.trackingErrMrad !== null ? s.trackingErrMrad.toFixed(3) : '',
      procMs: s.procMs.toFixed(2),
      fps: Math.round(s.fps),
      confirmedId: s.confirmedId !== null ? s.confirmedId : ''
    }));
  }

  return {
    addSample,
    onStateChange,
    reset,
    getSummary,
    getTimeSeries,
    exportRows,
    getSampleCount: () => samples.length
  };
}
