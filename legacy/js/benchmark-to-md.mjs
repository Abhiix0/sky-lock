#!/usr/bin/env node
/**
 * Benchmark Results to Markdown Converter.
 *
 * Reads a benchmark JSON output file and generates structured GitHub Flavored
 * Markdown tables containing run configurations and per-scenario statistical
 * summaries (Mean ± Std).
 *
 * Outputs to stdout and writes to docs/figures/benchmark-tables.md.
 *
 * Usage:
 *   node scripts/benchmark-to-md.mjs [path/to/benchmark.json]
 */

import fs from 'node:fs';
import path from 'node:path';

function computeStats(values) {
  const nums = (values || []).filter((v) => typeof v === 'number' && !Number.isNaN(v));
  if (nums.length === 0) return { mean: 0, std: 0 };
  const mean = nums.reduce((sum, v) => sum + v, 0) / nums.length;
  if (nums.length === 1) return { mean, std: 0 };
  const variance = nums.reduce((sum, v) => sum + (v - mean) ** 2, 0) / (nums.length - 1);
  return { mean, std: Math.sqrt(variance) };
}

function fmt(stat, decimals = 2) {
  if (!stat || typeof stat.mean !== 'number') return 'N/A';
  return `${stat.mean.toFixed(decimals)} ± ${stat.std.toFixed(decimals)}`;
}

function generateMarkdownTables(benchmarkData) {
  const { configSnapshot, runs, aggregate, timestamp, totalWallClockMs, environment } = benchmarkData;

  const lines = [];

  lines.push('# Sky Lock Benchmark Statistical Tables');
  lines.push('');
  lines.push(`- **Generated At**: \`${timestamp || new Date().toISOString()}\``);
  lines.push(`- **Total Wall-Clock Time**: \`${totalWallClockMs ? (totalWallClockMs / 1000).toFixed(1) : 'N/A'} s\``);
  lines.push(`- **Environment**: \`${environment ? environment.userAgent : 'Node.js'}\``);
  lines.push(`- **Total Scenario Runs**: \`${runs ? runs.length : 0}\` (8 scenarios × 3 seeds: Seeds [1, 2, 3])`);
  lines.push('');

  // 1. Run Configuration Table
  lines.push('## 1. Run Configuration Parameters');
  lines.push('');
  lines.push('| Parameter Category | Key / Subsystem | Configured Value | Unit | Description |');
  lines.push('| :--- | :--- | :--- | :--- | :--- |');

  if (configSnapshot) {
    const cam = configSnapshot.CAMERA_CONFIG || {};
    lines.push(`| Camera | \`resolution\` | ${cam.width || 640} × ${cam.height || 480} | px | Gimbal sensor optical matrix |`);
    lines.push(`| Camera | \`fovDeg\` | ${cam.fovDeg || 1.8} | deg | Narrow FOV tracking optic |`);
    lines.push(`| Camera | \`pixelScale\` | ${cam.pixelScaleMradPerPx ? (cam.pixelScaleMradPerPx * 1000).toFixed(2) : '0.436'} | µrad/px | Spatial angular resolution |`);
    lines.push(`| Actuator | \`slewRateMax\` | ${cam.slewRateDegPerSec || 15} | deg/s | Maximum 2-axis gimbal rate |`);
    lines.push(`| Actuator | \`slewAccelMax\` | ${cam.slewAccelDegPerSec2 || 30} | deg/s² | Maximum gimbal acceleration |`);

    const klm = configSnapshot.KALMAN_CONFIG || {};
    lines.push(`| Kalman Filter | \`qPos / qVel\` | ${klm.qPos || 0.05} / ${klm.qVel || 0.5} | - | Process noise covariance diagonal |`);
    lines.push(`| Kalman Filter | \`rPos\` | ${klm.rPos || 2.0} | px² | Measurement noise variance |`);

    const ctrl = configSnapshot.CONTROLLER_CONFIG || {};
    lines.push(`| Controller | \`kp / ki / kd\` | ${ctrl.kp || 1.8} / ${ctrl.ki || 0.15} / ${ctrl.kd || 0.35} | - | Discrete PID servo loop gains |`);
    lines.push(`| Controller | \`feedForward\` | ${ctrl.feedForwardEnabled !== false ? 'Enabled' : 'Disabled'} | - | State-prediction velocity feed-forward |`);

    const bcn = configSnapshot.BEACON_CODE || {};
    lines.push(`| Beacon ID | \`bitPeriodSec\` | ${bcn.bitPeriodSec || 0.25} | s | Optical Manchester pulse interval |`);
    lines.push(`| Beacon ID | \`codeSequence\` | \`0b${bcn.bits || '11010010'}\` | - | 8-bit unforgeable optical signature |`);
  } else {
    lines.push('| Global | Config snapshot | Standard Defaults | - | Baseline Sky Lock parameters |');
  }
  lines.push('');

  // Group runs by scenario ID
  const scenarioRunsMap = new Map();
  if (Array.isArray(runs)) {
    for (const r of runs) {
      const id = r.scenario ? r.scenario.id : 'S?';
      if (!scenarioRunsMap.has(id)) {
        scenarioRunsMap.set(id, []);
      }
      scenarioRunsMap.get(id).push(r);
    }
  }

  // 2. Performance Summary Table (Acquisition & Lock Retention)
  lines.push('## 2. Acquisition Time, Lock Retention & Reacquisition Performance');
  lines.push('');
  lines.push('| Scenario | Description | Disturbances | Decoys | Slew Mode | Acquisition Time (s) | Lock Retention (%) | Reacquisition Mean (s) | False Locks |');
  lines.push('| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |');

  for (const [id, sRuns] of scenarioRunsMap.entries()) {
    const firstSc = sRuns[0].scenario || {};
    const acqTimes = sRuns.map((r) => r.summary.acquisitionTimeSec).filter((v) => typeof v === 'number');
    const retentions = sRuns.map((r) => r.summary.lockRetentionRate).filter((v) => typeof v === 'number');
    const reacqMeans = sRuns.map((r) => r.summary.reacquisitionMeanSec).filter((v) => typeof v === 'number');
    const falseLocks = sRuns.reduce((sum, r) => sum + (r.summary.falseLocks || 0), 0);

    const acqStat = computeStats(acqTimes);
    const retStat = computeStats(retentions);
    const reacqStat = computeStats(reacqMeans);

    const desc = firstSc.name || id;
    const dist = firstSc.disturbancePreset || 'OFF';
    const decoys = firstSc.decoys ? 'Yes (3)' : 'No';
    const slew = firstSc.slewPreset || 'baseline';

    lines.push(
      `| **${id}** | ${desc} | \`${dist}\` | ${decoys} | \`${slew}\` | ${fmt(acqStat, 2)} | **${fmt(retStat, 1)}%** | ${fmt(reacqStat, 2)} | **${falseLocks}** |`
    );
  }
  lines.push('');

  // 3. Pointing Accuracy and Frame Latency Table
  lines.push('## 3. Pointing Error, System Latency & Frame Rate');
  lines.push('');
  lines.push('| Scenario | Pointing Err Mean (px) | Pointing Err RMS (px) | Pointing Err RMS (mrad) | Pointing Err Max (px) | Processing Latency (ms) | Render FPS |');
  lines.push('| :--- | :---: | :---: | :---: | :---: | :---: | :---: |');

  for (const [id, sRuns] of scenarioRunsMap.entries()) {
    const ptMeans = sRuns.map((r) => r.summary.pointingError?.meanPx).filter((v) => typeof v === 'number');
    const ptRmsPx = sRuns.map((r) => r.summary.pointingError?.rmsPx).filter((v) => typeof v === 'number');
    const ptRmsMrad = sRuns.map((r) => r.summary.pointingError?.rmsMrad).filter((v) => typeof v === 'number');
    const ptMaxPx = sRuns.map((r) => r.summary.pointingError?.maxPx).filter((v) => typeof v === 'number');
    const latMeans = sRuns.map((r) => r.summary.processingMs?.mean).filter((v) => typeof v === 'number');
    const fpsMeans = sRuns.map((r) => r.summary.fps?.mean).filter((v) => typeof v === 'number');

    const ptMeanStat = computeStats(ptMeans);
    const ptRmsPxStat = computeStats(ptRmsPx);
    const ptRmsMradStat = computeStats(ptRmsMrad);
    const ptMaxStat = computeStats(ptMaxPx);
    const latStat = computeStats(latMeans);
    const fpsStat = computeStats(fpsMeans);

    lines.push(
      `| **${id}** | ${fmt(ptMeanStat, 2)} | **${fmt(ptRmsPxStat, 2)}** | **${fmt(ptRmsMradStat, 3)}** | ${fmt(ptMaxStat, 1)} | ${fmt(latStat, 2)} | ${fmt(fpsStat, 1)} |`
    );
  }
  lines.push('');

  // 4. Per-Run Granular Data Appendix
  lines.push('## 4. Granular Scenario Run Log (All Seeds)');
  lines.push('');
  lines.push('| Scenario | Seed | Observable (s) | Tracked (s) | Retention (%) | Acq Time (s) | Pointing RMS (px) | Latency Mean (ms) |');
  lines.push('| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |');

  for (const r of runs || []) {
    const sc = r.scenario || {};
    const sm = r.summary || {};
    const pt = sm.pointingError || {};
    const pr = sm.processingMs || {};
    lines.push(
      `| ${sc.id} | ${sc.seed} | ${(sm.observableTimeSec || 0).toFixed(1)} | ${(sm.inTrackTimeSec || 0).toFixed(1)} | ${(sm.lockRetentionRate || 0).toFixed(1)}% | ${sm.acquisitionTimeSec !== null ? sm.acquisitionTimeSec.toFixed(2) : 'N/A'} | ${(pt.rmsPx || 0).toFixed(2)} | ${(pr.mean || 0).toFixed(2)} |`
    );
  }
  lines.push('');

  return lines.join('\n');
}

// CLI Execution
const args = process.argv.slice(2);
const defaultJsonPath = path.resolve('docs/figures/benchmark.json');
const targetJsonPath = args[0] ? path.resolve(args[0]) : defaultJsonPath;

if (!fs.existsSync(targetJsonPath)) {
  console.error(`❌ Input benchmark JSON not found at: ${targetJsonPath}`);
  console.error(`Usage: node scripts/benchmark-to-md.mjs <benchmark.json>`);
  process.exit(1);
}

try {
  const raw = fs.readFileSync(targetJsonPath, 'utf8');
  const data = JSON.parse(raw);
  const md = generateMarkdownTables(data);

  const outDir = path.resolve('docs/figures');
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  const outPath = path.join(outDir, 'benchmark-tables.md');
  fs.writeFileSync(outPath, md, 'utf8');
  console.log(`✅ Markdown tables successfully written to: ${outPath}`);
  console.log('\n' + md);
} catch (err) {
  console.error('❌ Failed to process benchmark JSON:', err);
  process.exit(1);
}
