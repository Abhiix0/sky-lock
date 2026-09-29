import { TRACKING_CONFIG, KALMAN_CONFIG, CAMERA_CONFIG } from './config.js';
import { raster, spiral } from './scanPatterns.js';
import { pixelToBodyAngles } from './geometry.js';

/**
 * Creates the FSOC acquisition and tracking state machine.
 *
 * States:
 *   SEARCH    - Sweeping space with raster pattern looking for beacon
 *   ACQUIRE   - Centering detected candidate and confirming across multiple frames
 *   TRACK     - Closed-loop Kalman-filtered line-of-sight tracking
 *   LOST      - Coastal propagation on Kalman dynamics during signal occlusion
 *   REACQUIRE - Expanding Archimedean spiral search around predicted line-of-sight
 *
 * @param {Object} [config=TRACKING_CONFIG]
 * @returns {Object} State machine instance
 */
export function createStateMachine(config = TRACKING_CONFIG) {
  const cfg = { ...TRACKING_CONFIG, ...config };

  let currentState = 'SEARCH';
  let stateStartTime = 0;
  let lastSeenTime = 0;

  let candidateAngles = { panDeg: 0, tiltDeg: 0 };
  let candidateConfirmCount = 0;

  let consecutiveMisses = 0;
  let spiralCenter = { panDeg: 0, tiltDeg: 0 };

  const eventLog = [];

  function transitionTo(nextState, simTime, reason) {
    if (nextState === currentState) return;

    const event = {
      type: 'STATE_CHANGE',
      from: currentState,
      to: nextState,
      simTime,
      reason
    };
    eventLog.push(event);

    currentState = nextState;
    stateStartTime = simTime;

    if (nextState === 'ACQUIRE') {
      candidateConfirmCount = 1;
      lastSeenTime = simTime;
    } else if (nextState === 'TRACK') {
      consecutiveMisses = 0;
      lastSeenTime = simTime;
    } else if (nextState === 'LOST') {
      consecutiveMisses = 0;
    }
  }

  /**
   * Process a detection frame update and determine next control target and state.
   *
   * @param {Object} inputs
   * @param {number} inputs.simTime - Simulation time in seconds
   * @param {Array<Object>} inputs.detections - Detected blobs from detector [{cx, cy, peak, snr, bbox}]
   * @param {Object} inputs.kalman - Kalman filter instance
   * @param {Object} inputs.gimbalState - Current gimbal telemetry {panDeg, tiltDeg, panRateDegS, tiltRateDegS}
   * @param {Object} [inputs.cameraCfg=CAMERA_CONFIG] - Camera configuration
   * @returns {{ state: string, mode: 'GOTO'|'TRACK', setpoint: { panDeg: number, tiltDeg: number }, selectedDetection: Object|null, events: Array<Object> }}
   */
  function update(inputs) {
    const {
      simTime,
      detections = [],
      kalman,
      gimbalState,
      cameraCfg = CAMERA_CONFIG
    } = inputs;

    const emittedEvents = [];
    const minSnr = cfg.minSnrSearch ?? 3.0;
    const gateSigma = KALMAN_CONFIG.gateThresholdSigma ?? 4.0;

    let selectedDetection = null;
    let mode = 'GOTO';
    let setpoint = { panDeg: gimbalState ? gimbalState.panDeg : 0, tiltDeg: gimbalState ? gimbalState.tiltDeg : 0 };

    // Find best candidate detection with highest peak/SNR
    const bestDetection = detections.length > 0
      ? detections.find((d) => d.snr >= minSnr) || detections[0]
      : null;

    switch (currentState) {
      case 'SEARCH': {
        const scan = raster(simTime - stateStartTime, cfg);
        setpoint = { panDeg: scan.panDeg, tiltDeg: scan.tiltDeg };
        mode = 'GOTO';

        if (bestDetection && bestDetection.snr >= minSnr) {
          selectedDetection = bestDetection;
          candidateAngles = pixelToBodyAngles(
            bestDetection.cx,
            bestDetection.cy,
            gimbalState.panDeg,
            gimbalState.tiltDeg,
            cameraCfg
          );
          transitionTo('ACQUIRE', simTime, 'Detection above SNR gate in SEARCH');
          emittedEvents.push(eventLog[eventLog.length - 1]);
        }
        break;
      }

      case 'ACQUIRE': {
        setpoint = { panDeg: candidateAngles.panDeg, tiltDeg: candidateAngles.tiltDeg };
        mode = 'GOTO';

        if (bestDetection && bestDetection.snr >= minSnr) {
          selectedDetection = bestDetection;
          candidateAngles = pixelToBodyAngles(
            bestDetection.cx,
            bestDetection.cy,
            gimbalState.panDeg,
            gimbalState.tiltDeg,
            cameraCfg
          );
          candidateConfirmCount++;
          lastSeenTime = simTime;

          if (candidateConfirmCount >= (cfg.acquireConfirmFrames ?? 3)) {
            if (kalman) {
              kalman.init(candidateAngles.panDeg, candidateAngles.tiltDeg, simTime);
            }
            transitionTo('TRACK', simTime, `Confirmed candidate over ${candidateConfirmCount} frames`);
            emittedEvents.push(eventLog[eventLog.length - 1]);
          }
        } else {
          if (simTime - lastSeenTime > (cfg.acquireTimeoutSec ?? 1.0)) {
            transitionTo('SEARCH', simTime, 'Acquire timeout without confirmation');
            emittedEvents.push(eventLog[eventLog.length - 1]);
          }
        }
        break;
      }

      case 'TRACK': {
        mode = 'TRACK';
        let bestGated = null;
        let minGateDist = Infinity;

        // Innovation gating against Kalman prediction
        if (kalman) {
          kalman.predict(simTime);

          for (const d of detections) {
            const bodyAngles = pixelToBodyAngles(
              d.cx,
              d.cy,
              gimbalState.panDeg,
              gimbalState.tiltDeg,
              cameraCfg
            );
            const gateDist = kalman.getInnovationGate(bodyAngles.panDeg, bodyAngles.tiltDeg);
            if (gateDist <= gateSigma && gateDist < minGateDist) {
              minGateDist = gateDist;
              bestGated = { detection: d, angles: bodyAngles };
            }
          }
        }

        if (bestGated) {
          selectedDetection = bestGated.detection;
          consecutiveMisses = 0;
          lastSeenTime = simTime;
          if (kalman) {
            kalman.update(bestGated.angles.panDeg, bestGated.angles.tiltDeg, simTime);
          }
        } else {
          consecutiveMisses++;
          if (consecutiveMisses > (cfg.lostMissFrames ?? 5)) {
            transitionTo('LOST', simTime, `Consecutive misses exceeded ${cfg.lostMissFrames}`);
            emittedEvents.push(eventLog[eventLog.length - 1]);
          }
        }

        if (kalman) {
          const kState = kalman.getState();
          setpoint = { panDeg: kState.panDeg, tiltDeg: kState.tiltDeg };
        }
        break;
      }

      case 'LOST': {
        mode = 'TRACK';
        if (kalman) {
          kalman.predict(simTime);
        }

        // Check if a gated detection reappears
        let recovered = null;
        if (kalman) {
          for (const d of detections) {
            if (d.snr < minSnr) continue;
            const bodyAngles = pixelToBodyAngles(
              d.cx,
              d.cy,
              gimbalState.panDeg,
              gimbalState.tiltDeg,
              cameraCfg
            );
            const gateDist = kalman.getInnovationGate(bodyAngles.panDeg, bodyAngles.tiltDeg);
            if (gateDist <= gateSigma) {
              recovered = { detection: d, angles: bodyAngles };
              break;
            }
          }
        }

        if (recovered) {
          selectedDetection = recovered.detection;
          if (kalman) {
            kalman.update(recovered.angles.panDeg, recovered.angles.tiltDeg, simTime);
          }
          transitionTo('TRACK', simTime, 'Reacquired detection within Kalman gate during coasting');
          emittedEvents.push(eventLog[eventLog.length - 1]);
        } else if (simTime - stateStartTime > (cfg.coastMaxSec ?? 14.0)) {
          if (kalman) {
            const ks = kalman.getState();
            spiralCenter = { panDeg: ks.panDeg, tiltDeg: ks.tiltDeg };
          } else {
            spiralCenter = { panDeg: gimbalState.panDeg, tiltDeg: gimbalState.tiltDeg };
          }
          transitionTo('REACQUIRE', simTime, `Coast duration exceeded ${cfg.coastMaxSec}s`);
          emittedEvents.push(eventLog[eventLog.length - 1]);
        }

        if (kalman) {
          const kState = kalman.getState();
          setpoint = { panDeg: kState.panDeg, tiltDeg: kState.tiltDeg };
        }
        break;
      }

      case 'REACQUIRE': {
        mode = 'GOTO';
        const scan = spiral(simTime - stateStartTime, spiralCenter, cfg);
        setpoint = { panDeg: scan.panDeg, tiltDeg: scan.tiltDeg };

        if (bestDetection && bestDetection.snr >= minSnr) {
          selectedDetection = bestDetection;
          candidateAngles = pixelToBodyAngles(
            bestDetection.cx,
            bestDetection.cy,
            gimbalState.panDeg,
            gimbalState.tiltDeg,
            cameraCfg
          );
          transitionTo('ACQUIRE', simTime, 'Detection found in REACQUIRE spiral');
          emittedEvents.push(eventLog[eventLog.length - 1]);
        } else if (scan.done) {
          transitionTo('SEARCH', simTime, 'Reacquire spiral completed without detection');
          emittedEvents.push(eventLog[eventLog.length - 1]);
        }
        break;
      }
    }

    return {
      state: currentState,
      mode,
      setpoint,
      selectedDetection,
      events: emittedEvents
    };
  }

  /**
   * Reset state machine to initial SEARCH state.
   *
   * @param {number} [simTime=0]
   */
  function reset(simTime = 0) {
    currentState = 'SEARCH';
    stateStartTime = simTime;
    lastSeenTime = simTime;
    candidateConfirmCount = 0;
    consecutiveMisses = 0;
    eventLog.length = 0;
  }

  return {
    getState: () => currentState,
    update,
    reset,
    getEvents: () => eventLog
  };
}
