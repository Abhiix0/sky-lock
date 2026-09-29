/**
 * Telemetry Head-Up Display (HUD) readout controller.
 * Displays live tracking state, lock duration, current pointing/tracking errors,
 * lock retention rate, processing time per frame, and render FPS.
 */

const STATE_CLASSES = {
  SEARCH: 'hud-state-search',
  ACQUIRE: 'hud-state-acquire',
  TRACK: 'hud-state-track',
  LOST: 'hud-state-lost',
  REACQUIRE: 'hud-state-reacquire'
};

/**
 * Creates the live HUD readout controller.
 *
 * @param {Object} elements - DOM elements for HUD display
 * @param {Object} metricsEngine - Metrics module instance
 * @returns {Object} HUD controller instance
 */
export function createHud(elements, metricsEngine) {
  const {
    stateEl,
    lockTimeEl,
    pointingErrEl,
    trackingErrEl,
    retentionEl,
    latencyEl,
    fpsEl
  } = elements;

  let lastAppliedState = null;

  /**
   * Update the HUD display elements with latest telemetry and metrics summary.
   *
   * @param {Object} [liveStatus={}] - Real-time tracking system status from trackingSystem.getStatus()
   */
  function update(liveStatus = {}) {
    if (!metricsEngine) return;

    const summary = metricsEngine.getSummary();
    const currentState = liveStatus.state || 'SEARCH';

    // 1. State badge
    if (stateEl) {
      stateEl.textContent = currentState;
      if (lastAppliedState !== currentState) {
        Object.values(STATE_CLASSES).forEach((cls) => stateEl.classList.remove(cls));
        const newCls = STATE_CLASSES[currentState];
        if (newCls) stateEl.classList.add(newCls);
        lastAppliedState = currentState;
      }
    }

    // 2. Lock time (total time in TRACK)
    if (lockTimeEl) {
      lockTimeEl.textContent = `${summary.inTrackTimeSec.toFixed(1)}s`;
    }

    // 3. Current Pointing Error
    if (pointingErrEl) {
      if (liveStatus.errPx !== null && liveStatus.errPx !== undefined && currentState === 'TRACK') {
        const mrad = liveStatus.errPx * 0.4363;
        pointingErrEl.textContent = `${liveStatus.errPx.toFixed(1)}px (${mrad.toFixed(2)}mrad)`;
      } else {
        pointingErrEl.textContent = '--';
      }
    }

    // 4. Current Tracking Error
    if (trackingErrEl) {
      const trMean = summary.trackingError ? summary.trackingError.meanPx : 0;
      if (trMean > 0 && currentState === 'TRACK') {
        trackingErrEl.textContent = `${trMean.toFixed(1)}px`;
      } else {
        trackingErrEl.textContent = '--';
      }
    }

    // 5. Lock retention rate
    if (retentionEl) {
      retentionEl.textContent = `${summary.lockRetentionRate.toFixed(1)}%`;
    }

    // 6. Processing latency
    if (latencyEl) {
      const detectMs = liveStatus.timings ? liveStatus.timings.detectMs : summary.processingMs.mean;
      latencyEl.textContent = `${Number(detectMs).toFixed(1)} ms`;
    }

    // 7. FPS
    if (fpsEl) {
      const fpsVal = summary.fps ? Math.round(summary.fps.mean) : 60;
      fpsEl.textContent = `${fpsVal}`;
    }
  }

  return {
    update
  };
}

/**
 * Automatically bind HUD DOM elements and start live telemetry updates.
 *
 * @param {Object} metricsEngine
 * @param {Object} trackingSystem
 * @returns {Object|null}
 */
export function initHudPanel(metricsEngine, trackingSystem) {
  const panelEl = document.getElementById('metrics-panel');
  if (!panelEl) return null;

  const collapseBtn = document.getElementById('metrics-collapse-btn');
  const bodyEl = document.getElementById('metrics-panel-body');
  if (collapseBtn && bodyEl) {
    collapseBtn.addEventListener('click', () => {
      const isHidden = bodyEl.style.display === 'none';
      bodyEl.style.display = isHidden ? 'flex' : 'none';
      collapseBtn.textContent = isHidden ? '−' : '+';
    });
  }

  const hud = createHud({
    stateEl: document.getElementById('hud-state'),
    lockTimeEl: document.getElementById('hud-lock-time'),
    pointingErrEl: document.getElementById('hud-pointing-err'),
    trackingErrEl: document.getElementById('hud-tracking-err'),
    retentionEl: document.getElementById('hud-retention'),
    latencyEl: document.getElementById('hud-latency'),
    fpsEl: document.getElementById('hud-fps')
  }, metricsEngine);

  setInterval(() => {
    const status = trackingSystem ? trackingSystem.getStatus() : {};
    hud.update(status);
  }, 100);

  return hud;
}
