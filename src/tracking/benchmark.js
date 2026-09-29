import { SCENARIOS, BENCHMARK_SEEDS } from './scenarios.js';
import { disturbances } from './disturbances.js';
import { exportBenchmark, computeAggregateTable } from './exporter.js';
import {
  CAMERA_CONFIG,
  TRACKING_CONFIG,
  KALMAN_CONFIG,
  CONTROLLER_CONFIG,
  DISTURBANCE_PRESETS,
  BEACON_CODE
} from './config.js';

/**
 * Runs a single simulation scenario in TURBO mode using requestAnimationFrame batches (~12ms each)
 * so the main UI thread never freezes.
 *
 * @param {Object} params
 * @param {Object} params.scenario - Scenario definition
 * @param {number} params.seed - PRNG seed
 * @param {Object} params.context - Global simulation context
 * @param {function(number): void} [params.onProgress] - Callback with progress in [0, 1]
 * @returns {Promise<Object>} Run result payload
 */
export function runScenario({ scenario, seed, context, onProgress }) {
  return new Promise((resolve) => {
    const wallStart = performance.now();
    const duration = scenario.durationSimSec || 190;
    const simSpeed = scenario.simSpeed || 1;
    const dt = (1 / 120) * simSpeed;
    const feedDt = 1 / 30;

    // 1. Reset Disturbances & PRNG
    disturbances.setSeed(seed);
    disturbances.setPreset(scenario.disturbancePreset);

    // 2. Configure Actuator & Decoys
    CAMERA_CONFIG.activeSlewPreset = scenario.slewPreset || 'baseline';
    if (context.gimbal && context.gimbal.setSlewPreset) {
      context.gimbal.setSlewPreset(scenario.slewPreset || 'baseline');
    }

    if (scenario.decoys) {
      if (context.beacon) {
        context.beacon.setMode('code');
        context.beacon.setCode(BEACON_CODE.bits, BEACON_CODE.bitPeriodSec);
      }
      if (context.decoys) {
        context.decoys.setEnabled(true);
        context.decoys.setCount(scenario.decoyCount || 3);
        context.decoys.setSeed(seed);
      }
    } else {
      if (context.beacon) {
        context.beacon.setMode('steady');
      }
      if (context.decoys) {
        context.decoys.setEnabled(false);
      }
    }

    // 3. Reset Simulation Clock & Orbits
    if (context.simClock) {
      context.simClock.reset();
    }
    const sats = context.getActiveSatellites ? context.getActiveSatellites() : [];
    sats.forEach((s) => {
      if (s.orbit && s.orbit.reset) s.orbit.reset();
    });

    // 4. Reset Tracking Subsystems
    const tracking = context.trackingSystem;
    if (tracking) {
      tracking.setMode('AUTO');
      if (tracking.stateMachine && tracking.stateMachine.reset) tracking.stateMachine.reset();
      if (tracking.controller && tracking.controller.reset) tracking.controller.reset();
      if (tracking.kalman && tracking.kalman.reset) tracking.kalman.reset();
      if (tracking.candidateTracker && tracking.candidateTracker.reset) tracking.candidateTracker.reset();
      if (tracking.metrics && tracking.metrics.reset) tracking.metrics.reset();
    }

    // Reset gimbal to initial bore-sight search pose
    if (context.gimbal && context.gimbal.snapTo) {
      context.gimbal.snapTo(90, 0);
    }

    let simTime = 0;
    let nextFeedTime = 0;

    function stepBatch() {
      const batchStart = performance.now();

      // Run as many simulation steps as fit within ~12ms time slice
      while (simTime < duration && performance.now() - batchStart < 12) {
        simTime += dt;

        // Step satellites on orbit
        sats.forEach((s) => {
          if (s.orbit && s.model) {
            s.orbit.update(dt, s.model);
          }
        });

        // Step observer & target beacons
        const s1 = sats.find((s) => s.id === 'S-1');
        const s2 = sats.find((s) => s.id === 'S-2');
        if (context.beacon && s2) {
          context.beacon.update(s2, simTime, s1);
        }
        if (context.decoys && s2 && s2.model) {
          context.decoys.update(simTime, s2.model.position);
        }

        // Actuate tracking controller & gimbal
        if (tracking) {
          tracking.step(dt);
        }
        if (context.gimbal) {
          context.gimbal.step(dt);
        }

        // Process sensor feed capture at 30 Hz
        if (simTime >= nextFeedTime) {
          nextFeedTime += feedDt;
          if (context.virtualCamera && s1 && s2) {
            context.virtualCamera.renderFeed(s1, simTime, s2);
            const feedFrame = context.virtualCamera.getFrame();
            if (feedFrame && tracking) {
              tracking.onFrame(feedFrame);
            }
          }
        }
      }

      if (onProgress) {
        onProgress(Math.min(1.0, simTime / duration));
      }

      if (simTime < duration) {
        requestAnimationFrame(stepBatch);
      } else {
        const wallClockMs = performance.now() - wallStart;
        const summary = tracking && tracking.metrics ? tracking.metrics.getSummary() : {};
        const timeSeries = tracking && tracking.metrics ? tracking.metrics.getTimeSeries(120) : [];

        resolve({
          scenario: {
            ...scenario,
            seed
          },
          summary,
          timeSeries,
          wallClockMs
        });
      }
    }

    requestAnimationFrame(stepBatch);
  });
}

/**
 * Execute full benchmark matrix across all scenarios and seeds.
 *
 * @param {Object} context - Global simulation context
 * @param {Object} [options={}]
 * @param {Array<Object>} [options.scenarios=SCENARIOS]
 * @param {Array<number>} [options.seeds=BENCHMARK_SEEDS]
 * @param {function(Object): void} [options.onProgress]
 * @param {function(Object): void} [options.onComplete]
 * @returns {Promise<Object>}
 */
export async function runBenchmark(context, options = {}) {
  const scenarios = options.scenarios || SCENARIOS;
  const seeds = options.seeds || BENCHMARK_SEEDS;
  const totalRuns = scenarios.length * seeds.length;
  let currentRunIndex = 0;
  const runs = [];

  const wallStartTotal = performance.now();

  for (let sIdx = 0; sIdx < scenarios.length; sIdx++) {
    const sc = scenarios[sIdx];
    for (let sSeedIdx = 0; sSeedIdx < seeds.length; sSeedIdx++) {
      const seed = seeds[sSeedIdx];
      currentRunIndex++;

      if (options.onProgress) {
        options.onProgress({
          scenario: sc,
          seed,
          runIndex: currentRunIndex,
          totalRuns,
          runProgress: 0
        });
      }

      const runResult = await runScenario({
        scenario: sc,
        seed,
        context,
        onProgress: (frac) => {
          if (options.onProgress) {
            options.onProgress({
              scenario: sc,
              seed,
              runIndex: currentRunIndex,
              totalRuns,
              runProgress: frac
            });
          }
        }
      });

      runs.push(runResult);
    }
  }

  const totalWallClockMs = performance.now() - wallStartTotal;
  const aggregate = computeAggregateTable(runs);

  const payload = {
    benchmarkVersion: '1.0.0',
    appVersion: '0.0.0',
    timestamp: new Date().toISOString(),
    totalWallClockMs,
    environment: {
      userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : 'Node.js',
      hardwareConcurrency: typeof navigator !== 'undefined' ? (navigator.hardwareConcurrency || 4) : 4,
      devicePixelRatio: typeof window !== 'undefined' ? (window.devicePixelRatio || 1) : 1
    },
    configSnapshot: {
      CAMERA_CONFIG: { ...CAMERA_CONFIG },
      TRACKING_CONFIG: { ...TRACKING_CONFIG },
      KALMAN_CONFIG: { ...KALMAN_CONFIG },
      CONTROLLER_CONFIG: { ...CONTROLLER_CONFIG },
      DISTURBANCE_PRESETS: { ...DISTURBANCE_PRESETS },
      BEACON_CODE: { ...BEACON_CODE }
    },
    runs,
    aggregate
  };

  // Export artifacts (JSON and CSV downloads)
  exportBenchmark(payload);

  if (options.onComplete) {
    options.onComplete(payload);
  }

  return payload;
}

/**
 * Determinism Check: executes scenario S2 twice with identical seed 42.
 * Verifies that the outputs match exactly bit-for-bit / within floating-point epsilon.
 *
 * @param {Object} context - Simulation context
 * @returns {Promise<{ passed: boolean, diffs: Array<string> }>}
 */
export async function runDeterminismCheck(context) {
  const s2 = SCENARIOS.find((s) => s.id === 'S2') || {
    id: 'S2',
    name: 'Medium Disturbances',
    durationSimSec: 75,
    disturbancePreset: 'MED',
    decoys: false,
    simSpeed: 1,
    slewPreset: 'baseline'
  };

  // Shorten check to 75 seconds (~1 full orbit cycle) for fast test
  const checkScenario = { ...s2, durationSimSec: 75 };
  const seed = 42;

  console.log('[Determinism Check] Starting Run 1 (S2, seed 42)...');
  const run1 = await runScenario({ scenario: checkScenario, seed, context });

  console.log('[Determinism Check] Starting Run 2 (S2, seed 42)...');
  const run2 = await runScenario({ scenario: checkScenario, seed, context });

  const diffs = [];
  const sm1 = run1.summary;
  const sm2 = run2.summary;

  const compareField = (name, val1, val2, eps = 1e-4) => {
    if (Math.abs((val1 || 0) - (val2 || 0)) > eps) {
      diffs.push(`${name}: Run 1 = ${val1}, Run 2 = ${val2}`);
    }
  };

  compareField('observableTimeSec', sm1.observableTimeSec, sm2.observableTimeSec);
  compareField('inTrackTimeSec', sm1.inTrackTimeSec, sm2.inTrackTimeSec);
  compareField('lockRetentionRate', sm1.lockRetentionRate, sm2.lockRetentionRate);
  compareField('acquisitionTimeSec', sm1.acquisitionTimeSec, sm2.acquisitionTimeSec);
  compareField('reacquisitionMeanSec', sm1.reacquisitionMeanSec, sm2.reacquisitionMeanSec);
  compareField('pointingError.rmsPx', sm1.pointingError?.rmsPx, sm2.pointingError?.rmsPx);
  compareField('falseLocks', sm1.falseLocks, sm2.falseLocks);

  const passed = diffs.length === 0;
  if (passed) {
    console.log('[Determinism Check] PASS: Run 1 and Run 2 produced identical metrics.');
  } else {
    console.error('[Determinism Check] FAIL: Discrepancies detected between runs:', diffs);
  }

  return { passed, diffs };
}
