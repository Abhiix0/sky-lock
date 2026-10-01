/**
 * Benchmark data exporter for Sky Lock.
 * Exports comprehensive JSON and CSV logs, with an overrideable saveFile seam
 * for browser Blob downloads or Electron native filesystem saving.
 */

/**
 * Default browser file download implementation.
 * Can be overridden by Electron via setSaveFileHandler().
 *
 * @param {string} filename - Filename with extension
 * @param {Blob|Uint8Array} data - File content
 */
let saveFileHandler = async (filename, data) => {
  if (
    typeof window !== 'undefined' &&
    window.skylock &&
    typeof window.skylock.saveFile === 'function'
  ) {
    let uint8;
    if (data instanceof Uint8Array) {
      uint8 = data;
    } else if (data instanceof Blob) {
      const buffer = await data.arrayBuffer();
      uint8 = new Uint8Array(buffer);
    } else if (typeof data === 'string') {
      uint8 = new TextEncoder().encode(data);
    } else {
      uint8 = new Uint8Array(data);
    }
    return window.skylock.saveFile(filename, uint8);
  }

  const blob = data instanceof Blob ? data : new Blob([data], { type: 'application/octet-stream' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
};

/**
 * Configure custom file persistence handler (used by Electron).
 *
 * @param {function(string, Blob|Uint8Array): Promise<void>|void} handler
 */
export function setSaveFileHandler(handler) {
  if (typeof handler === 'function') {
    saveFileHandler = handler;
  }
}

/**
 * Single saveFile entry point.
 *
 * @param {string} filename
 * @param {Blob|Uint8Array} data
 */
export function saveFile(filename, data) {
  return saveFileHandler(filename, data);
}

/**
 * Computes mean and sample standard deviation of an array of numbers.
 *
 * @param {Array<number>} values
 * @returns {{ mean: number, std: number }}
 */
export function computeMeanStd(values) {
  if (!values || values.length === 0) return { mean: 0, std: 0 };
  const n = values.length;
  const mean = values.reduce((sum, v) => sum + v, 0) / n;
  if (n <= 1) return { mean, std: 0 };
  const variance = values.reduce((sum, v) => sum + (v - mean) ** 2, 0) / (n - 1);
  return { mean, std: Math.sqrt(variance) };
}

/**
 * Generates an aggregate summary table grouping runs by scenario.
 * Computes mean +/- std across seeds for headline metrics.
 *
 * @param {Array<Object>} runs - List of run objects
 * @returns {Object} Aggregated scenario statistics
 */
export function computeAggregateTable(runs) {
  const byScenario = {};

  for (const r of runs) {
    const id = r.scenario.id;
    if (!byScenario[id]) {
      byScenario[id] = {
        id,
        name: r.scenario.name,
        retention: [],
        pointingRmsPx: [],
        acqTime: [],
        reacqMean: [],
        procLatency: [],
        falseLocks: []
      };
    }

    const s = r.summary;
    byScenario[id].retention.push(s.lockRetentionRate || 0);
    byScenario[id].pointingRmsPx.push(s.pointingError ? s.pointingError.rmsPx : 0);
    byScenario[id].acqTime.push(s.acquisitionTimeSec || 0);
    byScenario[id].reacqMean.push(s.reacquisitionMeanSec || 0);
    byScenario[id].procLatency.push(s.processingMs ? s.processingMs.mean : 0);
    byScenario[id].falseLocks.push(s.falseLocks || 0);
  }

  const result = {};
  for (const [id, data] of Object.entries(byScenario)) {
    result[id] = {
      scenarioId: id,
      name: data.name,
      retention: computeMeanStd(data.retention),
      pointingRmsPx: computeMeanStd(data.pointingRmsPx),
      acqTime: computeMeanStd(data.acqTime),
      reacqMean: computeMeanStd(data.reacqMean),
      procLatency: computeMeanStd(data.procLatency),
      falseLocks: computeMeanStd(data.falseLocks)
    };
  }

  return result;
}

/**
 * Format benchmark runs as a standard CSV file according to docs/BENCHMARK_SCHEMA.md.
 *
 * @param {Array<Object>} runs
 * @returns {string} CSV text
 */
export function formatBenchmarkCsv(runs) {
  const headers = [
    'scenario_id',
    'scenario_name',
    'seed',
    'duration_sim_sec',
    'wall_clock_ms',
    'sim_speed',
    'disturbance_preset',
    'decoys_enabled',
    'slew_preset',
    'observable_time_sec',
    'track_time_sec',
    'lock_retention_pct',
    'acq_time_sec',
    'acq_from_start_sec',
    'reacq_count',
    'reacq_mean_sec',
    'reacq_max_sec',
    'pointing_err_mean_px',
    'pointing_err_rms_px',
    'pointing_err_p95_px',
    'pointing_err_max_px',
    'pointing_err_mean_mrad',
    'pointing_err_rms_mrad',
    'pointing_err_p95_mrad',
    'tracking_err_mean_px',
    'tracking_err_rms_px',
    'false_locks',
    'proc_latency_mean_ms',
    'proc_latency_p95_ms',
    'render_fps_mean',
    'dropped_frames'
  ];

  const escapeCsv = (val) => {
    if (val === null || val === undefined) return '';
    const str = String(val);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const rows = [headers.join(',')];

  for (const r of runs) {
    const sc = r.scenario;
    const sm = r.summary;
    const pt = sm.pointingError || {};
    const tr = sm.trackingError || {};
    const pr = sm.processingMs || {};
    const fps = sm.fps || {};

    const values = [
      sc.id,
      sc.name,
      sc.seed,
      sc.durationSimSec,
      r.wallClockMs ? r.wallClockMs.toFixed(1) : '',
      sc.simSpeed,
      sc.disturbancePreset,
      sc.decoys ? 'true' : 'false',
      sc.slewPreset,
      sm.observableTimeSec ? sm.observableTimeSec.toFixed(2) : '0.00',
      sm.inTrackTimeSec ? sm.inTrackTimeSec.toFixed(2) : '0.00',
      sm.lockRetentionRate ? sm.lockRetentionRate.toFixed(2) : '0.00',
      sm.acquisitionTimeSec !== null ? sm.acquisitionTimeSec.toFixed(2) : '',
      sm.acquisitionFromStartSec !== null ? sm.acquisitionFromStartSec.toFixed(2) : '',
      sm.reacquisitions ? sm.reacquisitions.length : 0,
      sm.reacquisitionMeanSec ? sm.reacquisitionMeanSec.toFixed(2) : '0.00',
      sm.reacquisitionMaxSec ? sm.reacquisitionMaxSec.toFixed(2) : '0.00',
      pt.meanPx ? pt.meanPx.toFixed(2) : '0.00',
      pt.rmsPx ? pt.rmsPx.toFixed(2) : '0.00',
      pt.p95Px ? pt.p95Px.toFixed(2) : '0.00',
      pt.maxPx ? pt.maxPx.toFixed(2) : '0.00',
      pt.meanMrad ? pt.meanMrad.toFixed(3) : '0.000',
      pt.rmsMrad ? pt.rmsMrad.toFixed(3) : '0.000',
      pt.p95Mrad ? pt.p95Mrad.toFixed(3) : '0.000',
      tr.meanPx ? tr.meanPx.toFixed(2) : '0.00',
      tr.rmsPx ? tr.rmsPx.toFixed(2) : '0.00',
      sm.falseLocks || 0,
      pr.mean ? pr.mean.toFixed(2) : '0.00',
      pr.p95 ? pr.p95.toFixed(2) : '0.00',
      fps.mean ? fps.mean.toFixed(1) : '60.0',
      sm.droppedFrames || 0
    ];

    rows.push(values.map(escapeCsv).join(','));
  }

  return rows.join('\n');
}

/**
 * Export benchmark logs as JSON and CSV downloads.
 *
 * @param {Object} benchmarkPayload
 * @param {string} [timestamp] - ISO timestamp string
 */
export function exportBenchmark(
  benchmarkPayload,
  timestamp = new Date().toISOString().replace(/[:.]/g, '-')
) {
  const jsonName = `benchmark-${timestamp}.json`;
  const csvName = `benchmark-${timestamp}.csv`;

  const jsonStr = JSON.stringify(benchmarkPayload, null, 2);
  const jsonBlob = new Blob([jsonStr], { type: 'application/json' });
  saveFile(jsonName, jsonBlob);

  if (benchmarkPayload.runs) {
    const csvStr = formatBenchmarkCsv(benchmarkPayload.runs);
    const csvBlob = new Blob([csvStr], { type: 'text/csv' });
    saveFile(csvName, csvBlob);
  }
}
