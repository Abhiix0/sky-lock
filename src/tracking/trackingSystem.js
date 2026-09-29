import { createDetector } from './detector.js';
import { createKalmanFilter } from './kalman.js';
import { createController } from './controller.js';
import { createStateMachine } from './stateMachine.js';
import { bodyAnglesToPixel } from './geometry.js';
import { CAMERA_CONFIG, DETECTOR_CONFIG, BEACON_CODE, ID_CONFIG } from './config.js';
import { disturbances } from './disturbances.js';
import { createCandidateTracker } from './candidateTracker.js';
import { evaluateCandidates, getConfirmedCandidate } from './beaconId.js';
import { createMetrics } from './metrics.js';

/**
 * Creates the closed-loop autonomous tracking system.
 *
 * Coordinates detector, Kalman filter, PID rate controller, candidate tracker,
 * blink-code ID, and acquisition state machine through the Tracking API.
 *
 * @param {Object} api - Tracking API boundary interface
 * @param {Object} [options={}]
 * @returns {Object} Tracking system instance
 */
export function createTrackingSystem(api, options = {}) {
  const detector = createDetector(options.detectorConfig);
  const kalman = createKalmanFilter(options.kalmanConfig);
  const controller = createController(options.controllerConfig);
  const stateMachine = createStateMachine(options.trackingConfig);
  const candidateTracker = createCandidateTracker(options.idConfig);
  const metrics = options.metrics || createMetrics(options.metricsConfig);

  let evaluatedCandidates = [];
  let confirmedCandidate = null;

  let mode = 'AUTO'; // 'AUTO' | 'MANUAL'
  let lastProcessedFrameId = -1;
  let smResult = null;
  let lastDetResult = null;

  // Ring buffer for timing metrics (last 30 frames)
  const timingBuffer = new Float32Array(30);
  let timingIndex = 0;
  let timingCount = 0;

  /**
   * Process incoming camera frame (called when frame.frameId advances).
   *
   * @param {Object} frame - Camera frame payload
   */
  function onFrame(frame) {
    if (!frame || frame.frameId === lastProcessedFrameId) return;
    lastProcessedFrameId = frame.frameId;

    const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
    const gimbalState = api.getGimbalState();
    const currentState = stateMachine.getState();

    // In AUTO mode and TRACK state: restrict detection to ROI around Kalman predicted pixel
    let roi;
    if (mode === 'AUTO' && currentState === 'TRACK') {
      const pred = kalman.getState();
      const proj = bodyAnglesToPixel(
        pred.panDeg,
        pred.tiltDeg,
        gimbalState.panDeg,
        gimbalState.tiltDeg,
        CAMERA_CONFIG
      );

      if (proj.inFrustum) {
        const margin = DETECTOR_CONFIG.roiMarginPx || 40;
        roi = {
          x: proj.px - margin,
          y: proj.py - margin,
          w: margin * 2,
          h: margin * 2
        };
      }
    }

    // 0. Disturbance sensor stage (noise, hot pixels, blur) applied to frame copy
    disturbances.applySensorStage(frame);

    // 1. Blob detection on post-disturbance frame
    lastDetResult = detector.detect(frame, roi ? { roi } : undefined);

    // 2. Multi-candidate tracking and blink-code ID evaluation (Phase 3B)
    let kalmanPredPx = null;
    if (kalman && currentState === 'TRACK') {
      const pred = kalman.getState();
      const proj = bodyAnglesToPixel(
        pred.panDeg,
        pred.tiltDeg,
        gimbalState.panDeg,
        gimbalState.tiltDeg,
        CAMERA_CONFIG
      );
      if (proj.inFrustum) {
        kalmanPredPx = { x: proj.px, y: proj.py };
      }
    }

    const rawCandidates = candidateTracker.update(
      lastDetResult.blobs,
      frame.timestamp,
      kalmanPredPx
    );
    evaluatedCandidates = evaluateCandidates(
      rawCandidates,
      options.beaconCode || BEACON_CODE,
      options.idConfig || ID_CONFIG
    );
    confirmedCandidate = getConfirmedCandidate(evaluatedCandidates);

    // 3. State machine update (feeding identified candidate)
    smResult = stateMachine.update({
      simTime: frame.timestamp,
      detections: lastDetResult.blobs,
      confirmedCandidate,
      strongestCandidate: evaluatedCandidates[0] || null,
      allCandidates: evaluatedCandidates,
      kalman,
      gimbalState,
      cameraCfg: CAMERA_CONFIG
    });

    const t1 = typeof performance !== 'undefined' ? performance.now() : Date.now();
    const frameProcMs = t1 - t0;

    timingBuffer[timingIndex] = frameProcMs;
    timingIndex = (timingIndex + 1) % timingBuffer.length;
    if (timingCount < timingBuffer.length) timingCount++;

    // 4. Emit sample to performance metrics engine
    const gt = api.getGroundTruth ? api.getGroundTruth() : null;
    let estimatePx = null;
    if (kalman && gimbalState) {
      const pred = kalman.getState();
      const proj = bodyAnglesToPixel(
        pred.panDeg,
        pred.tiltDeg,
        gimbalState.panDeg,
        gimbalState.tiltDeg,
        CAMERA_CONFIG
      );
      if (proj.inFrustum) {
        estimatePx = { x: proj.px, y: proj.py };
      }
    }

    metrics.addSample({
      simTime: frame.timestamp,
      state: stateMachine.getState(),
      groundTruth: gt
        ? {
            pixelX: gt.pixelX,
            pixelY: gt.pixelY,
            inFrustum: gt.inFrustum,
            losClear: gt.losClear !== undefined ? gt.losClear : true,
            reachable: gt.reachable !== undefined ? gt.reachable : true
          }
        : { pixelX: 0, pixelY: 0, inFrustum: false, losClear: true, reachable: true },
      estimatePx,
      detectionPx:
        smResult && smResult.selectedDetection
          ? { x: smResult.selectedDetection.cx, y: smResult.selectedDetection.cy }
          : null,
      procMs: frameProcMs,
      fps: typeof window !== 'undefined' && window.__skyFps ? window.__skyFps : 60,
      confirmedId: confirmedCandidate ? confirmedCandidate.id : null,
      droppedFrames: disturbances.getDroppedFramesCount ? disturbances.getDroppedFramesCount() : 0
    });
  }

  /**
   * Fixed simulation step callback for controller and gimbal actuation.
   *
   * @param {number} dt - Timestep in seconds
   */
  function step(dt) {
    if (dt <= 0) return;

    if (mode !== 'AUTO') return;

    const gimbalState = api.getGimbalState();
    const simTime = api.getSimTime();
    const currentState = stateMachine.getState();

    if (currentState === 'SEARCH' || currentState === 'ACQUIRE' || currentState === 'REACQUIRE') {
      // In search/acquire, command angles via go-to setpoints
      if (smResult && smResult.setpoint) {
        api.setGimbalCommand(smResult.setpoint.panDeg, smResult.setpoint.tiltDeg);
      }
    } else {
      // In TRACK or LOST, drive gimbal rates smoothly with PID plus feed-forward
      kalman.predict(simTime);
      const kState = kalman.getState();

      const ctrlOut = controller.step(dt, {
        gimbalPanDeg: gimbalState.panDeg,
        gimbalTiltDeg: gimbalState.tiltDeg,
        losEstimate: { panDeg: kState.panDeg, tiltDeg: kState.tiltDeg },
        losRateEstimate: { panRateDegS: kState.panRateDegS, tiltRateDegS: kState.tiltRateDegS }
      });

      api.setGimbalRateCommand(ctrlOut.panRateDegS, ctrlOut.tiltRateDegS);
    }
  }

  /**
   * Set tracking operation mode.
   *
   * @param {'AUTO'|'MANUAL'} newMode
   */
  function setMode(newMode) {
    mode = newMode === 'MANUAL' ? 'MANUAL' : 'AUTO';
    if (mode === 'MANUAL') {
      controller.reset();
      // Leave gimbal in current position or controlled by manual keys
      api.setGimbalRateCommand(0, 0);
    }
  }

  /**
   * Compute median processing latency from timing ring buffer.
   *
   * @returns {number}
   */
  function getMedianProcessingMs() {
    if (timingCount === 0) return 0;
    const sorted = Array.from(timingBuffer.subarray(0, timingCount)).sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length / 2)];
  }

  /**
   * Get telemetry and diagnostics status.
   *
   * @returns {Object}
   */
  function getStatus() {
    const kState = kalman.getState();
    const gt = api.getGroundTruth();
    const selected = smResult ? smResult.selectedDetection : null;

    let errPx = null;
    if (gt && gt.inFrustum && selected) {
      errPx = Math.hypot(gt.pixelX - selected.cx, gt.pixelY - selected.cy);
    }

    return {
      state: stateMachine.getState(),
      mode,
      detection: selected,
      confirmedId: confirmedCandidate ? confirmedCandidate.id : null,
      candidates: evaluatedCandidates,
      estimate: {
        panDeg: kState.panDeg,
        tiltDeg: kState.tiltDeg,
        panRateDegS: kState.panRateDegS,
        tiltRateDegS: kState.tiltRateDegS,
        sigmaDeg: kalman.getPositionSigmaDeg()
      },
      gtPixel: gt ? { pixelX: gt.pixelX, pixelY: gt.pixelY, inFrustum: gt.inFrustum } : null,
      errPx,
      timings: {
        detectMs: lastDetResult ? lastDetResult.processingMs : 0,
        recentMedianMs: getMedianProcessingMs()
      },
      metrics: metrics.getSummary()
    };
  }

  return {
    onFrame,
    step,
    setMode,
    getMode: () => mode,
    getStatus,
    detector,
    kalman,
    controller,
    stateMachine,
    candidateTracker,
    metrics,
    disturbances
  };
}
