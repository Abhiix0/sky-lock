# SkyLock Benchmark Framework Specification & Guide

**Document ID:** `DOC-BENCH-001`  
**Classification:** Technical Architecture & Reference Guide  
**Version:** `1.0`  
**Target System:** SkyLock Optical Tracking Rebuild  

---

## 1. Overview & Principles

The SkyLock Benchmark Framework provides a completely deterministic, isolated, provenance-complete benchmarking environment for evaluating the optical tracking pipeline under controlled synthetic scenarios and real video recordings.

### Core Architectural Principles

1. **Strict GUI Independence**: The benchmark framework is completely headless. It never imports `PySide6`, `Qt`, or any GUI-related component. Running tests or benchmarks in headless CI environments requires no display server (X11/Wayland).
2. **Deterministic Execution**: Given the same scenario configuration and integer seed, running the benchmark twice produces identical per-frame hash signatures and metric records within floating-point tolerance ($10^{-9}$).
3. **Execution Isolation**: Runs can be executed in isolated subprocesses (via `multiprocessing.get_context("spawn")`), ensuring zero residual memory or state leakage between consecutive runs (e.g. S05 followed by S01 produces identical results to S01 executed in isolation).
4. **Honest Measurement & Verdicts**: The framework never uses synthetic fallback defaults (e.g. `fps || 60` or `0` for missing data). Scenarios that fail requirements report honest `FAIL` verdicts; scenarios lacking required input (e.g. absent MP4 video) produce `NOT_RUN`, never synthesized passes.
5. **Full Provenance**: Every run record captures git commit SHA, platform metadata, Python and library versions, full config overrides, seed, and execution timestamps.

---

## 2. Built-in Benchmark Scenarios

The benchmark catalog (`skylock.benchmark.catalog.builtin_scenarios()`) defines 16 standardized scenarios covering baseline motion, disturbance stress testing, and real video playback:

| ID | Description | Duration | Input | Key Tags |
|---|---|---|---|---|
| **S01_line_clean** | Clean baseline: constant velocity linear motion (5 deg/s) across FOV | 4.0 s | Simulation | `baseline`, `clean` |
| **S02_circle_clean** | Clean baseline: circular orbit (0.8 deg radius, 8.0 s period) | 6.0 s | Simulation | `baseline`, `clean` |
| **S03_figure8_clean** | Clean baseline: Lissajous figure-8 trajectory | 8.0 s | Simulation | `baseline`, `clean` |
| **S04_stop_and_go** | High jerk: periodic acceleration/deceleration steps (2 s period) | 6.0 s | Simulation | `dynamics`, `jerk` |
| **S05_line_spec_noise** | PS_SPEC maximum sensor noise ($\sigma=20$, salt & pepper $0.01$, Poisson photon scale $10$) | 4.0 s | Simulation | `noise`, `stress` |
| **S06_hot_pixels** | Fixed defective camera pixels: 20 hot/dead pixel locations | 4.0 s | Simulation | `sensor`, `defect` |
| **S07_lens_flare** | Solar glare artifact: radius 60 px at intensity 255.0 moving across FOV | 4.0 s | Simulation | `optical`, `glare` |
| **S08_turbulence** | Atmospheric turbulence: optical blur kernel $\sigma=3.0$, intensity flicker | 4.0 s | Simulation | `atmosphere`, `blur` |
| **S09_fog** | Atmospheric fog attenuation: transmission $0.2$, airlight $180.0$ (very low contrast) | 4.0 s | Simulation | `atmosphere`, `fog` |
| **S10_vibration** | Platform jitter / gimbal base motion: $50\text{ Hz}$ sine $0.05^\circ$ + random walk | 4.0 s | Simulation | `jitter`, `platform` |
| **S11_step_disturbance** | Wind gust impulse: $2.0^\circ$ angular step at $t = 2.0\text{ s}$ | 4.0 s | Simulation | `gust`, `impulse` |
| **S12_cloud_occlusion** | Cloud bank crossing target: complete occlusion between $t=1.5\text{ s}$ and $t=2.5\text{ s}$ | 5.0 s | Simulation | `occlusion` |
| **S13_all_disturbances** | Comprehensive stress test: noise + hot pixels + blur + vibration combined | 4.0 s | Simulation | `combined`, `stress` |
| **S14_multi_target** | Distractor target: primary linear target plus secondary orbiting target | 6.0 s | Simulation | `multi_target`, `clutter` |
| **S15_slew10** | High gimbal dynamics: slew limit elevated to $10.0^\circ/\text{s}$, accel $25^\circ/\text{s}^2$ | 4.0 s | Simulation | `gimbal`, `fast` |
| **S16_mp4** | Video replay: external MP4 recording through identical tracking pipeline | End-of-file | MP4 Video | `video`, `real` |

*Note: If `data/flight_test.mp4` is not present on disk, S16 safely returns status `NOT_RUN` with reason `"MP4 file not found: ..."`.*

---

## 3. Benchmark Runner Architecture

### 3.1 Execution Flow

The runner (`skylock.benchmark.runner.BenchmarkRunner`) manages test execution through the following pipeline:

```
[Scenario + Seed]
       │
       ▼
 [apply(base_cfg, seed)] ───► Derived deterministic RNG seeds
       │
       ▼
 [cv2.setNumThreads(1)]  ───► Single-threaded OpenCV determinism
       │
       ▼
 [Build Session]         ───► SimulationSource / Mp4Source -> Pipeline -> Controller
       │
       ▼
 [Execute Steps]         ───► Computes per-frame image MD5 & trajectory SHA-256
       │
       ▼
 [Collector.finalize()]  ───► Metrics evaluated against cfg.requirements
       │
       ▼
 [RunRecord]             ───► Provenance, hashes, metrics, verdicts, wall time
```

### 3.2 In-Process vs Subprocess Isolation

- **In-Process Mode (`isolate=False`)**: Executes directly in the host Python process. Fast for unit tests and local iteration.
- **Process Isolation Mode (`isolate=True`)**: Spawns a clean Python worker process via `multiprocessing.get_context("spawn")`. Eliminates static state retention, C library state (OpenCV/NumPy), and memory fragmentation.

---

## 4. CLI Usage

The benchmark suite is accessible via the `skylock bench` CLI subcommand or the `scripts/run_benchmark.py` wrapper.

### Syntax

```bash
python -m skylock.app.cli bench [OPTIONS]
# or
python scripts/run_benchmark.py [OPTIONS]
```

### Command-Line Arguments

| Flag | Type | Description |
|---|---|---|
| `--all` | Flag | Execute all 16 catalog scenarios. |
| `--scenarios` / `-s` | Strings | Comma- or space-separated list of scenario IDs (e.g. `S01_line_clean,S02_circle_clean`). |
| `--seeds` | Integers | Space-separated random seed integers (default: `[42]`). |
| `--out` / `-o` | Path | Output directory for `report.json` and `report.md` (default: `runs/benchmark`). |
| `--isolate` | Flag | Execute each run in a separate spawned process. |
| `--fail-on-verdict` | Flag | Exit with code 1 if any scenario evaluates to `FAIL`. |
| `--mp4` | Path | Custom path for MP4 input video in scenario `S16_mp4`. |

### Example Invocations

```bash
# Smoke test on baseline line scenario
python scripts/run_benchmark.py --scenarios S01_line_clean --seeds 1 --out runs/smoke

# Run full baseline suite with process isolation
python scripts/run_benchmark.py --scenarios S01_line_clean,S02_circle_clean,S03_figure8_clean --isolate

# Run entire catalog across multiple seeds
python scripts/run_benchmark.py --all --seeds 42 123 999 --out runs/release_validation
```

---

## 5. Report Formats & Schemas

The runner writes two output files to the target directory:

### 5.1 JSON Report (`report.json`)

Follows schema version `1.0`:
- **`schema_version`**: `"1.0"`
- **`generated_at`**: ISO-8601 UTC timestamp
- **`summary`**:
  - `total_runs`: Integer
  - `verdict_counts`: Tally of `{PASS, FAIL, INDETERMINATE, NOT_RUN}`
  - `aggregated`: Per-metric mean, rms, min, max, and `n` (only over `MEASURED` values)
- **`runs`**: List of run records containing:
  - `scenario_id`, `seed`, `status`, `overall_verdict`
  - `provenance`: Git commit, host platform, Python version, OpenCV version
  - `frames`: Frame count executed
  - `wall_time_s`: Execution duration in seconds
  - `frame_hash`: Cumulative MD5 hash of processed frames
  - `trajectory_hash`: SHA-256 hash of output trajectory estimates
  - `metrics`: Full metric records with status, value (`null` if unmeasured), and reason
  - `verdicts`: Individual requirement verdicts

### 5.2 Markdown Report (`report.md`)

Human-readable Markdown document including:
- Run metadata & system environment
- High-level verdict summary
- Results table with key performance indicators (Acquisition Time, Tracking Error RMS, Target Loss Rate)

---

## 6. Regression Testing & Run Comparison

The `skylock.benchmark.compare` module enables automated comparison between benchmark runs:

```python
from skylock.benchmark.compare import compare_runs

# Compare two RunRecords with a numerical tolerance
diffs = compare_runs(record_baseline, record_candidate, tol=1e-9)

if diffs:
    print(f"Detected {len(diffs)} regressions / discrepancies:")
    for diff in diffs:
        print(f"  [{diff.field}] baseline={diff.value_a} candidate={diff.value_b} ({diff.reason})")
```

The comparator ignores non-deterministic fields (`wall_time_s`, timestamps) while strictly verifying:
- Scenario ID and seed equality
- Frame count equality
- Exact frame hash and trajectory hash match
- Metric statuses and numerical values within floating-point tolerance
- Verdict consistency
