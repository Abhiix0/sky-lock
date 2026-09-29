/**
 * Fixed-timestep simulation clock for deterministic, FPS-independent simulation.
 */

/**
 * Creates a fixed-timestep simulation clock.
 *
 * @param {Object} [options]
 * @param {number} [options.stepHz=120] - Number of fixed steps per simulation second
 * @returns {Object} simClock interface
 */
export function createSimClock({ stepHz = 120 } = {}) {
  const fixedDt = 1 / stepHz;
  let simTime = 0;
  let accumulator = 0;

  /**
   * Advance simulation clock using real delta time and time scale.
   *
   * @param {number} realDtSec - Elapsed real wall-clock time in seconds
   * @param {number} timeScale - Simulation speed multiplier (0 when paused)
   * @param {Function} onStep - Callback invoked for each fixed step with (fixedDt, simTime)
   */
  function advance(realDtSec, timeScale, onStep) {
    if (timeScale <= 0 || realDtSec <= 0) return;

    // Accumulate scaled delta time
    accumulator += realDtSec * timeScale;

    // Guard against spiral of death: maximum 16 steps per frame
    const maxSteps = 16;
    let stepCount = 0;

    while (accumulator >= fixedDt) {
      accumulator -= fixedDt;
      simTime += fixedDt;
      stepCount++;

      if (onStep) {
        onStep(fixedDt, simTime);
      }

      if (stepCount >= maxSteps) {
        // Discard any excess accumulator to prevent spiral of death
        accumulator = 0;
        break;
      }
    }
  }

  /**
   * Monotonic simulation time in seconds.
   * @returns {number}
   */
  function getSimTime() {
    return simTime;
  }

  /**
   * Reset simulation clock to zero.
   */
  function reset() {
    simTime = 0;
    accumulator = 0;
  }

  return {
    advance,
    getSimTime,
    reset,
    fixedDt
  };
}
