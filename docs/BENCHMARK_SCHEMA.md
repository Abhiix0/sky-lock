# Sky Lock Benchmark Schema Specification

This document details the file formats and column definitions for JSON and CSV logs exported by the Sky Lock automated benchmark harness (`src/tracking/benchmark.js` & `src/tracking/exporter.js`).

---

## 1. Export Formats

Each benchmark execution exports two timestamped artifact files:
- `benchmark-<ISO_TIMESTAMP>.json`: Complete hierarchic benchmark telemetry including environment configurations, per-run metadata, detailed statistical distributions, and decimated time series.
- `benchmark-<ISO_TIMESTAMP>.csv`: Flat tabular summary containing one row per (scenario, seed) run, optimized for data frames, analysis scripts (Python pandas / R), and CI verification.

---

## 2. CSV Schema (One Row Per Run)

The CSV file includes a header row followed by one row for each evaluated scenario and seed combination:

| Column Name | Data Type | Units | Description |
|:---|:---|:---|:---|
| `scenario_id` | String | -- | Scenario identifier (e.g., `S0`, `S1`, ..., `S7`) |
| `scenario_name` | String | -- | Human-readable scenario name |
| `seed` | Integer | -- | Mulberry32 PRNG seed utilized for the run |
| `duration_sim_sec` | Float | s | Total scenario simulation duration |
| `wall_clock_ms` | Float | ms | Real wall-clock execution time elapsed during turbo run |
| `sim_speed` | Float | x | Simulation speed multiplier (e.g. 1.0, 4.0) |
| `disturbance_preset` | String | -- | Disturbance preset: `OFF`, `LOW`, `MED`, or `HIGH` |
| `decoys_enabled` | Boolean | -- | Whether optical decoys were active |
| `slew_preset` | String | -- | Actuator rate preset: `baseline` (45 deg/s) or `ps` (30 deg/s) |
| `observable_time_sec` | Float | s | Total time line-of-sight was clear and target within gimbal limits |
| `track_time_sec` | Float | s | Total duration the autonomous state machine spent in `TRACK` |
| `lock_retention_pct` | Float | % | Percentage of observable time maintained in `TRACK` within lock radius (30 px) |
| `acq_time_sec` | Float | s | Duration from first observable instant to first entry into `TRACK` |
| `acq_from_start_sec` | Float | s | Elapsed scenario time to first `TRACK` entry |
| `reacq_count` | Integer | -- | Number of occlusion recovery cycles completed |
| `reacq_mean_sec` | Float | s | Mean duration from target emergence to re-entering `TRACK` |
| `reacq_max_sec` | Float | s | Maximum reacquisition duration recorded across all occlusions |
| `pointing_err_mean_px` | Float | px | Mean pointing error from sensor center to true target during `TRACK` |
| `pointing_err_rms_px` | Float | px | Root-mean-square pointing error during `TRACK` |
| `pointing_err_p95_px` | Float | px | 95th percentile pointing error during `TRACK` |
| `pointing_err_max_px` | Float | px | Maximum pointing error during `TRACK` |
| `pointing_err_mean_mrad` | Float | mrad | Mean pointing error converted to milliradians (0.43633 mrad/px) |
| `pointing_err_rms_mrad` | Float | mrad | RMS pointing error in milliradians |
| `pointing_err_p95_mrad` | Float | mrad | 95th percentile pointing error in milliradians |
| `tracking_err_mean_px` | Float | px | Mean error between Kalman state estimate and true target position |
| `tracking_err_rms_px` | Float | px | RMS tracking error between Kalman state estimate and ground truth |
| `false_locks` | Integer | -- | Count of false-lock events (> 1.0s in TRACK with error > 50 px) |
| `proc_latency_mean_ms` | Float | ms | Mean image detection and tracking processing time per feed frame |
| `proc_latency_p95_ms` | Float | ms | 95th percentile processing latency per feed frame |
| `render_fps_mean` | Float | fps | Mean visual renderer frames per second during execution |
| `dropped_frames` | Integer | -- | Cumulative count of dropped camera feed frames |

---

## 3. JSON Schema Specification

The JSON export conforms to the following schema:

```json
{
  "benchmarkVersion": "1.0.0",
  "appVersion": "0.0.0",
  "timestamp": "2026-09-29T19:30:00.000Z",
  "environment": {
    "userAgent": "...",
    "hardwareConcurrency": 8,
    "devicePixelRatio": 1
  },
  "configSnapshot": {
    "CAMERA_CONFIG": { ... },
    "TRACKING_CONFIG": { ... },
    "KALMAN_CONFIG": { ... },
    "CONTROLLER_CONFIG": { ... },
    "DISTURBANCE_PRESETS": { ... },
    "BEACON_CODE": { ... }
  },
  "runs": [
    {
      "scenario": {
        "id": "S0",
        "name": "Clean Baseline",
        "seed": 1,
        "durationSimSec": 190,
        "disturbancePreset": "OFF",
        "decoys": false,
        "simSpeed": 1,
        "slewPreset": "baseline"
      },
      "summary": { ... },
      "timeSeries": [
        { "simTime": 0.0, "state": "SEARCH", "pointingErrPx": null, "procMs": 1.2 }
      ]
    }
  ],
  "aggregate": {
    "S0": {
      "lockRetentionMean": 97.4,
      "lockRetentionStd": 0.1,
      "pointingErrRmsPxMean": 4.2,
      "pointingErrRmsPxStd": 0.05
    }
  }
}
```
