/**
 * Lightweight canvas-based line charts and state timeline strip for Sky Lock.
 * Zero external libraries, high performance, updates at 5 Hz.
 */

const STATE_COLORS = {
  SEARCH: '#3b82f6', // Blue
  ACQUIRE: '#f59e0b', // Amber
  TRACK: '#22c55e', // Green
  LOST: '#ef4444', // Red
  REACQUIRE: '#a855f7' // Purple
};

/**
 * Creates and manages the telemetry charts.
 *
 * @param {Object} elements
 * @param {HTMLCanvasElement} elements.errorCanvas - Pointing error chart canvas
 * @param {HTMLCanvasElement} elements.latencyCanvas - Processing latency chart canvas
 * @param {HTMLCanvasElement} elements.timelineCanvas - State timeline strip canvas
 * @param {Object} metricsEngine - Metrics module instance from createMetrics()
 * @returns {Object} Charts controller instance
 */
export function createCharts({ errorCanvas, latencyCanvas, timelineCanvas }, metricsEngine) {
  let timerId = null;
  const WINDOW_SEC = 60.0; // Last 60 seconds of history
  
  // Track last known dimensions to avoid unnecessary resizes
  const lastDimensions = new Map();

  function resizeCanvas(canvas) {
    if (!canvas) return false;

    // Use offsetWidth/offsetHeight which respect the CSS fixed height constraints.
    // getBoundingClientRect().height can drift if the canvas element itself is
    // the thing growing — offsetHeight reads the CSS-constrained layout size.
    const cssW = canvas.offsetWidth;
    const cssH = canvas.offsetHeight;
    if (cssW === 0 || cssH === 0) return false;

    const dpr = window.devicePixelRatio || 1;
    const targetW = Math.round(cssW * dpr);
    const targetH = Math.round(cssH * dpr);

    // Only resize if dimensions actually changed — prevents feedback loop
    const key = canvas.id || canvas;
    const last = lastDimensions.get(key);
    if (last && last.w === targetW && last.h === targetH) {
      return false;
    }

    canvas.width = targetW;
    canvas.height = targetH;
    lastDimensions.set(key, { w: targetW, h: targetH });
    return true;
  }

  // Resize all canvases only on window resize events, never on every redraw tick
  function handleResize() {
    resizeCanvas(errorCanvas);
    resizeCanvas(latencyCanvas);
    resizeCanvas(timelineCanvas);
  }

  // Initial sizing — runs once after construction
  handleResize();

  // Only re-size when the window itself changes dimensions
  window.addEventListener('resize', handleResize);

  /**
   * Redraw all three chart components.
   */
  function redraw() {
    if (!metricsEngine) return;

    const samples = metricsEngine.getTimeSeries(300);
    if (samples.length === 0) return;

    const latestTime = samples[samples.length - 1].simTime;
    const startTime = Math.max(0, latestTime - WINDOW_SEC);

    // Filter samples within the 60s sliding window
    const windowSamples = samples.filter((s) => s.simTime >= startTime);
    if (windowSamples.length === 0) return;

    drawErrorChart(windowSamples, startTime, latestTime);
    drawLatencyChart(windowSamples, startTime, latestTime);
    drawTimelineStrip(windowSamples, startTime, latestTime);
  }

  function drawErrorChart(samples, tMin, tMax) {
    if (!errorCanvas) return;
    const ctx = errorCanvas.getContext('2d');
    if (!ctx) return;

    const w = errorCanvas.width;
    const h = errorCanvas.height;
    ctx.clearRect(0, 0, w, h);

    // Background grid & threshold line (30 px lock radius)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
    ctx.fillRect(0, 0, w, h);

    const maxErr = 60; // Max Y-scale = 60 px
    const lockRadiusPx = 30;
    const lockY = h - (lockRadiusPx / maxErr) * h;

    // Draw lock radius guide
    ctx.strokeStyle = 'rgba(239, 68, 68, 0.35)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, lockY);
    ctx.lineTo(w, lockY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw error curve
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    let started = false;

    for (let i = 0; i < samples.length; i++) {
      const s = samples[i];
      if (s.pointingErrPx === null) {
        started = false;
        continue;
      }
      const x = ((s.simTime - tMin) / (tMax - tMin || 1)) * w;
      const y = h - (Math.min(maxErr, s.pointingErrPx) / maxErr) * (h - 4) - 2;

      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    // Chart label
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px monospace';
    ctx.fillText('ERR (px)', 4, 11);
    ctx.fillStyle = 'rgba(239, 68, 68, 0.7)';
    ctx.fillText('30px', w - 28, lockY - 2);
  }

  function drawLatencyChart(samples, tMin, tMax) {
    if (!latencyCanvas) return;
    const ctx = latencyCanvas.getContext('2d');
    if (!ctx) return;

    const w = latencyCanvas.width;
    const h = latencyCanvas.height;
    ctx.clearRect(0, 0, w, h);

    ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
    ctx.fillRect(0, 0, w, h);

    const maxMs = 5.0; // 5ms top scale
    const budgetY = h - (3.0 / maxMs) * h; // 3ms budget line

    // Draw 3ms budget line
    ctx.strokeStyle = 'rgba(234, 179, 8, 0.35)';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(0, budgetY);
    ctx.lineTo(w, budgetY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw latency curve
    ctx.strokeStyle = '#34d399';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    let started = false;

    for (let i = 0; i < samples.length; i++) {
      const s = samples[i];
      const x = ((s.simTime - tMin) / (tMax - tMin || 1)) * w;
      const y = h - (Math.min(maxMs, s.procMs) / maxMs) * (h - 4) - 2;

      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px monospace';
    ctx.fillText('PROC (ms)', 4, 11);
    ctx.fillStyle = 'rgba(234, 179, 8, 0.7)';
    ctx.fillText('3ms', w - 24, budgetY - 2);
  }

  function drawTimelineStrip(samples, tMin, tMax) {
    if (!timelineCanvas) return;
    const ctx = timelineCanvas.getContext('2d');
    if (!ctx) return;

    const w = timelineCanvas.width;
    const h = timelineCanvas.height;
    ctx.clearRect(0, 0, w, h);

    const totalDur = tMax - tMin || 1;

    for (let i = 0; i < samples.length; i++) {
      const s = samples[i];
      const nextTime = i < samples.length - 1 ? samples[i + 1].simTime : tMax;
      const x = ((s.simTime - tMin) / totalDur) * w;
      const blockW = Math.max(1, ((nextTime - s.simTime) / totalDur) * w);

      const color = STATE_COLORS[s.state] || '#64748b';
      ctx.fillStyle = color;
      ctx.fillRect(x, 0, blockW, h);
    }
  }

  function start(fps = 5) {
    if (timerId !== null) return;
    const intervalMs = Math.round(1000 / fps);
    timerId = setInterval(redraw, intervalMs);
  }

  function stop() {
    if (timerId !== null) {
      clearInterval(timerId);
      timerId = null;
    }
    window.removeEventListener('resize', handleResize);
  }

  return {
    redraw,
    start,
    stop
  };
}

/**
 * Automatically bind chart canvas DOM elements and start 5 Hz updates.
 *
 * @param {Object} metricsEngine
 * @returns {Object|null}
 */
export function initChartsPanel(metricsEngine) {
  const errorCanvas = document.getElementById('chart-error');
  const latencyCanvas = document.getElementById('chart-latency');
  const timelineCanvas = document.getElementById('chart-timeline');

  if (!errorCanvas || !latencyCanvas || !timelineCanvas) return null;

  const charts = createCharts({ errorCanvas, latencyCanvas, timelineCanvas }, metricsEngine);
  charts.start(5);
  return charts;
}
