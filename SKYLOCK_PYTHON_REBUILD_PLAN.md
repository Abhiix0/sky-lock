# SkyLock Python Rebuild — Master Implementation Plan

> Save this file in the repo as `docs/MASTER_PLAN.md` before running Phase 0. Every Antigravity prompt below refers to it.

---

## 0. ZIP Inspection — Audit Verification

Inspected `sky-lock-main.zip` (extracts to `sky-lock-Pycon/`, 100 files, no `.git`). I ran the existing Python tests (`90 passed`). I did **not** execute the JS runtime (no Node run), so JS runtime behaviour claims below are from reading code and the committed `docs/figures/benchmark.json`.

| Audit claim | Verdict | Evidence |
|---|---|---|
| JS/Three.js/Electron runtime | **Confirmed** | `src/main.js`, `sceneSetup.js`, `orbit.js`, `electron/`, `vite.config.js`, `three@0.170` |
| Python package has algorithm modules only | **Confirmed** | `src/skylock/`: config, geometry, gimbal, kalman, detector, candidate_tracker, state_machine, scan_patterns, controller, disturbances, beacon_id. No camera, pipeline, GUI, metrics, benchmark, video, entry point, PyInstaller spec |
| JS uses 20° FOV, 45°/s slew | **Confirmed** | `src/tracking/config.js`: `fovDeg: 20`, `maxSlewRateDegPerSec: 45`; benchmark.json config snapshot agrees |
| JS camera RGBA/colour | **Confirmed** | offscreen WebGL FBO; detector default mode is chroma (`min(R,B)-G`) |
| Python config already matches PS | **Nuance (audit did not say)** | `skylock/config.py`: FOV 4°×3°, 640×480, 30 Hz, 5°/s, noise σ cap 20. But it is fed by module-level singletons (`CAMERA = CameraConfig()` used as default arguments) |
| Python detector is not monochrome | **New finding** | `skylock/detector.py` default `mode="chroma"`, expects BGR `(H,W,3)` |
| MP4 input missing | **Confirmed** | no `VideoCapture` anywhere |
| Motion models straight/circular/figure-8/random missing | **Confirmed** | target is a satellite orbit (`orbit.js`) |
| Disturbances incomplete | **Confirmed** | Python `disturbances.py` has OFF/LOW/MED/HIGH presets with wander, scintillation, hot pixels, frame drops; **no** salt-and-pepper, Poisson, atmosphere modes (haze/fog/rain/low light), platform motion |
| Benchmark results invalid | **Confirmed** | `docs/figures/benchmark.json`: 24 runs. Run 1: 190 s, `firstTrackTime: null`, `inTrackTimeSec: 0`, yet `pointingError` and `reacquisitionMeanSec` are `0`. Other runs: `totalSimTimeSec: 0` |
| Metrics contain misleading fallbacks | **Confirmed** | `metrics.js`: `fps: sample.fps \|\| 60`, `meanFps … : 60`, `procMs \|\| 0`; empty error stats serialised as `0` |
| LOST → REACQUIRE broken | **Partially verified, and the real problem is worse** | `stateMachine.js` LOST→REACQUIRE happens only after `coastMaxSec` (10 s) of *non-occluded* time. That is 10× the 1 s requirement. More seriously, `trackingSystem.js:117-129` calls `api.getGroundTruth()` and passes `losOccluded` into the state machine → **ground truth leaks into a tracking decision**. Not executed, so "broken at runtime" is unverified |
| Duplicated JS/Python logic | **Confirmed** | every Python module carries a `JS reference:` header |
| Tests unit-level only | **Confirmed** | 11 JS + 10 Python unit files; nothing runs sim→track→control end to end |
| README stale | **New finding** | claims 43 tests, describes Three.js/Electron |

Derived design constants (these drive several decisions):

- IFOV = 4°/640 = 3°/480 = **0.00625°/px** (square pixels).
- 5°/s slew = **26.7 px/frame** at 30 Hz; 10°/s = **53 px/frame**. ±20 px jitter = 0.125°/frame.
- In 2 s the gimbal at 5°/s can move only 10°. "Acquisition ≤ 2 s" is therefore only achievable if the target starts inside or near the FOV. The plan defines acquisition relative to a scenario-declared initial offset and reports both "from start" and "from first observable" (see §3, §6 metrics).
- Kalman/tracker state must be usable when there is **no gimbal** (MP4). Hence tracker coordinates are *sky-frame angles = pointing telemetry + pixel offset × IFOV*, with fixed pointing `(0,0)` for MP4.

---

## 1. Final Architecture

```
sky-lock/
├── pyproject.toml
├── README.md
├── src/skylock/
│   ├── __init__.py            # __version__ only
│   ├── __main__.py            # python -m skylock
│   ├── app/                   # composition + entry points (no algorithms)
│   │   ├── main.py            # main(): `skylock gui | run | bench`
│   │   ├── cli.py
│   │   ├── session.py         # Session: builds source+pipeline+controller+metrics from config; step()/run()
│   │   └── factory.py         # build_source(cfg), build_pipeline(cfg)
│   ├── config/                # ONE authoritative config
│   │   ├── models.py          # frozen dataclasses, __post_init__ validation
│   │   ├── validation.py      # cross-field rules, ConfigError (aggregates all violations)
│   │   ├── io.py              # to_dict/from_dict/JSON, snapshot(), config_hash()
│   │   └── presets.py         # named override sets (spec_default, disturbance presets)
│   ├── core/                  # dependency-free contracts (numpy + stdlib only)
│   │   ├── types.py           # Frame, Pointing, Detection, Candidate, TargetEstimate, ControlIntent, ControlCommand, GroundTruthSample, PipelineOutput
│   │   ├── enums.py           # TrackState, MetricStatus, Verdict, InputKind
│   │   ├── interfaces.py      # Protocols: FrameSource, Detector, GimbalPlant
│   │   ├── geometry.py        # wrap_deg, pixel<->angle (tangent-plane), IFOV helpers
│   │   ├── rng.py             # derive_rng(seed, "component") via SeedSequence.spawn
│   │   ├── pipeline.py        # TrackingPipeline: Frame -> PipelineOutput (no GT, no sim imports)
│   │   └── errors.py
│   ├── vision/                # image -> detections (classical CV)
│   │   ├── preprocess.py      # denoise, background estimate
│   │   ├── detector.py        # ClassicalBlobDetector (implements Detector)
│   │   └── centroid.py        # intensity-weighted sub-pixel centroid
│   ├── tracking/              # detections -> target state
│   │   ├── kalman.py          # 4-state CV filter (NumPy)
│   │   ├── candidate_tracker.py  # association, M-of-N confirmation
│   │   ├── search_patterns.py # raster (SEARCH), local spiral (REACQUIRE)
│   │   ├── state_machine.py   # SEARCH/ACQUIRE/TRACK/LOST/REACQUIRE
│   │   └── tracker.py         # Tracker = candidates + Kalman + state machine
│   ├── control/               # estimate -> command (hardware-agnostic)
│   │   ├── pid.py
│   │   └── controller.py      # PointingController: ControlIntent + estimate -> ControlCommand
│   ├── simulation/            # everything that fakes the physical world
│   │   ├── motion.py          # Line, Circle, Figure8, RandomWalk trajectories
│   │   ├── targets.py         # TargetSpec, shapes, visibility windows
│   │   ├── camera.py          # VirtualCamera: sky + pointing -> mono frame
│   │   ├── gimbal.py          # VirtualGimbal (implements GimbalPlant): slew/accel/limits
│   │   ├── disturbances/      # base.py noise.py jitter.py platform.py atmosphere.py blur.py stack.py
│   │   ├── ground_truth.py    # builds GroundTruthSample (side channel only)
│   │   └── source.py          # SimulationSource (implements FrameSource)
│   ├── input/
│   │   ├── video.py           # Mp4Source (implements FrameSource)
│   │   └── sources.py         # source registry helpers
│   ├── metrics/
│   │   ├── status.py          # Metric[T], MetricStatus semantics
│   │   ├── collector.py       # MetricsCollector.record(output, frame_meta, gt|None)
│   │   ├── calculators.py     # pure functions per metric
│   │   ├── requirements.py    # pass/fail vs RequirementsConfig -> PASS/FAIL/INDETERMINATE
│   │   └── logger.py          # JSONL/CSV per-frame log
│   ├── benchmark/
│   │   ├── scenario.py        # Scenario dataclass (id, overrides, duration, seed policy)
│   │   ├── catalog.py         # built-in scenarios
│   │   ├── runner.py          # BenchmarkRunner (process-isolated optional)
│   │   ├── report.py          # JSON + Markdown
│   │   └── compare.py         # determinism comparison
│   └── ui/                    # PySide6 presentation ONLY
│       ├── main_window.py, panels/*.py, widgets/*.py
│       └── worker.py          # QThread wrapping Session
├── tests/  {unit, integration, e2e, benchmark, architecture, fixtures}
├── scripts/  {gen_test_video.py, run_benchmark.py, check_architecture.py, build_exe.py}
├── packaging/skylock.spec
├── docs/  {MASTER_PLAN.md, ARCHITECTURE.md, PS_SPEC.md, CONFIG.md, METRICS.md, BENCHMARK.md, USER_GUIDE.md}
└── legacy/                    # TEMPORARY (Phase 0 → deleted Phase 12): old JS + old Python for reference
```

### Package responsibilities and import rules

| Package | Responsibility | May import | Must NOT import |
|---|---|---|---|
| `core` | Contracts, geometry, RNG helper, `TrackingPipeline` | stdlib, numpy, `config` (types only) | everything else |
| `config` | Typed config + validation | stdlib | all others |
| `vision` | Frame → `Detection[]` | `core`, `config`, cv2 | `simulation`, `metrics`, `tracking`, `control`, `ui` |
| `tracking` | Detections → `TargetEstimate` + `TrackState` + `ControlIntent` | `core`, `config` | `simulation`, `metrics`, `input`, `ui` |
| `control` | Estimate/intent → command | `core`, `config` | `simulation`, `metrics`, `ui` |
| `simulation` | Fake world: targets, camera, gimbal, disturbances | `core`, `config` | `tracking`, `vision`, `control`, `metrics`, `ui` |
| `input` | MP4 → Frame | `core`, `config`, cv2 | `simulation`, `tracking`, `ui` |
| `metrics` | Scoring; the **only** consumer of `GroundTruthSample` | `core`, `config` | `ui` |
| `benchmark` | Deterministic scenario execution | `app`, `metrics`, `config` | `ui` |
| `app` | Wiring, `Session`, CLI | everything except `ui` | `ui` |
| `ui` | Qt presentation | `app`, `config`, `core` types | — (nothing imports `ui`) |

These rules are enforced by an AST-based test (`tests/architecture/test_import_boundaries.py`, created in Phase 1, extended each phase).

---

## 2. Data Flow

### 2.1 Runtime loop

```
 SIMULATION PATH                                       MP4 PATH
 ───────────────                                       ────────
 TargetSpec+Trajectory ─┐                              .mp4 file
 VirtualGimbal(pointing)─┤                                 │  cv2.VideoCapture
 VirtualCamera.render() ─┤                                 │  BGR→gray, resize? (no: native size)
 DisturbanceStack ───────┘                                 ▼
        │                                            Mp4Source.read()
        ▼                                                  │
 SimulationSource.read()                                   │
   ├── Frame  ─────────────────────┐        ┌──────────────┘
   └── GroundTruthSample (side)    ▼        ▼
            │                 ┌────────────────────┐
            │                 │   Frame API        │  Frame(image: uint8 HxW read-only,
            │                 │   (core.types)     │        index, timestamp_s, source_id,
            │                 └─────────┬──────────┘        pointing: Pointing|None,  # encoder telemetry
            │                           ▼                    meta: Mapping[str,float|str])   # NO ground truth
            │                  TrackingPipeline.process(frame)
            │                    Detector (vision)
            │                    → Candidate generation / association
            │                    → Kalman predict/update
            │                    → StateMachine → TrackState, ControlIntent
            │                    → PipelineOutput(estimate, state, detections, intent, latency_ms)
            │                           │
            │                           ▼
            │                  PointingController.step(output, dt) → ControlCommand (pan/tilt rate)
            │                           │
            │            (sim only)     ▼
            │                  VirtualGimbal.command(cmd) → next pointing → VirtualCamera → next Frame
            │                  (MP4: command computed & logged, NOT applied — camera is the video)
            ▼
 METRICS PATH (separate):
   GroundTruthSample ───────────►┐
   PipelineOutput + Frame.meta ─►├─► MetricsCollector ─► RunMetrics ─► RequirementsEvaluator ─► verdicts
   wall-clock latency ──────────►┘                                    └► logger (JSONL)
```

### 2.2 Ground-truth firewall

1. `GroundTruthSample` is **not a field of `Frame`** and is only returned by `SimulationSource.read_with_truth()`.
2. `TrackingPipeline`, `Tracker`, `PointingController`, `ClassicalBlobDetector` have no parameter, attribute or import that can carry it.
3. `Session` is the only place both meet: it hands `Frame` to the pipeline and `(PipelineOutput, GroundTruthSample|None)` to `MetricsCollector`.
4. Architecture test: (a) AST scan — `vision/ tracking/ control/ core/pipeline.py` never import `skylock.simulation` or `skylock.metrics`, never reference the identifier `GroundTruthSample`; (b) a "poisoned truth" test — run the same seed twice where the sim's ground-truth values are deliberately corrupted after rendering; pipeline outputs must be bit-identical.
5. Allowed sensor telemetry (not truth): gimbal encoder `Pointing(pan_deg, tilt_deg)` at exposure time. For MP4 `pointing=None` ⇒ pipeline substitutes fixed `(0,0)`.

### 2.3 Time model

- Sim advances in **frame steps** of `1/camera.fps`; the gimbal integrates `camera.gimbal_substeps` (default 4) sub-steps per frame. Timestamp = `index / fps` (exact, deterministic). Wall-clock time is measured separately (`perf_counter`) only for latency/FPS metrics and is excluded from determinism comparisons.
- Control latency: command computed from frame *k* is applied starting at frame *k+1* (`control.latency_frames`, default 1).

---

## 3. Configuration Architecture

**One authoritative model:** `skylock.config.models.SkyLockConfig` — a tree of frozen dataclasses. No module-level default instances; nothing imports a global. Every component takes its own sub-config in its constructor. Overrides use `dataclasses.replace`; scenarios are override sets on the root config.

```python
@dataclass(frozen=True)
class SkyLockConfig:
    camera: CameraConfig
    target: TargetSetConfig        # list[TargetConfig], count, shapes
    motion: MotionConfig           # per-target motion params live in TargetConfig.motion (MotionConfig union)
    detection: DetectionConfig
    tracking: TrackingConfig
    control: ControlConfig
    gimbal: GimbalConfig
    disturbances: DisturbanceConfig
    input: InputConfig             # kind: "simulation" | "mp4"; mp4 path; assumed FOV for MP4
    requirements: RequirementsConfig   # PS targets (the ONLY place 2 s / 10 px / 5 % / 1 s / 20 FPS appear)
    seed: int
```

| Section | Key fields (defaults) |
|---|---|
| `camera` | `width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0, fps=30.0, monochrome=True, bit_depth=8`; derived `ifov_h_deg`, `ifov_v_deg` |
| `gimbal` | `slew_rate_deg_s=5.0, max_slew_rate_deg_s=10.0, accel_deg_s2=120.0, pan_limit_deg=(-45,45), tilt_limit_deg=(-30,30), initial=(0,0), substeps=4` |
| `target` | `count=1`, per target: `size_px=10, shape=square|disc|gaussian|cross|custom_mask, brightness=220, initial="random|fixed"` (+ position), `motion`, `visibility_windows` |
| motion (per target) | `kind=line|circle|figure8|random`; line: `speed_deg_s, heading_deg`; circle: `radius_deg, period_s, phase`; fig-8: `width_deg, height_deg, period_s`; random: `speed_deg_s, correlation_s, bounds_deg` |
| `detection` | `method=classical`, `blur_sigma=1.0, threshold_k_sigma=5.0, abs_min_threshold=25, min_area_px=6, max_area_px=900, max_blobs=8, roi_margin_px=48, median_filter=True` |
| `tracking` | `confirm_hits=3, confirm_window=5, acquire_timeout_s=1.0, lost_after_misses=5, coast_max_s=0.5, reacquire_timeout_s=1.0, reacquire_radius_deg=1.0, association_gate_px=30, gate_sigma=4.0, kalman q_accel_deg_s2, r_meas_px, search: field_of_regard_deg, raster_overlap=0.2, scan_rate_deg_s=4.0` |
| `control` | `kp, ki, kd, kff, d_filter_alpha, integral_clamp, deadband_px, latency_frames=1, mode=AUTO|MANUAL` |
| `disturbances` | independent components, each `{enabled, params}`: `salt_pepper{density}`, `gaussian{sigma_levels}`, `poisson{photon_scale}`, `camera_jitter{max_px_frame, correlation}`, `platform{kind=linear, velocity_px_frame, max_px_frame}`, `atmosphere{mode=clear|haze|fog|rain|low_light, strength}`, `blur{sigma_px}` |
| `input` | `kind`, `mp4_path`, `mp4_assumed_fov_h_deg` (default = camera FOV), `loop=False` |
| `requirements` | `acquisition_max_s=2.0, tracking_error_px_max=10.0, tracking_error_statistic="rms", target_loss_rate_max=0.05, reacquisition_max_s=1.0, processing_fps_min=20.0, lock_radius_px=10.0` |

### Validation rules (`__post_init__` per section + `validate_root()` for cross-field)

`ConfigError` aggregates **all** violations in one exception.

- Camera: `width,height ≥ 32`; `fov_* in (0, 180)`; **square-pixel check** `|ifov_h − ifov_v| / ifov_h ≤ 1 %`; `fps ≥ 30` (spec) unless `allow_below_spec_fps=True` (test-only escape hatch, recorded in snapshot).
- Gimbal: `0 < slew_rate ≤ max_slew_rate ≤ 10`; limits ordered; `accel > 0`.
- Target: `5 ≤ size_px ≤ 20` (spec) unless `strict_spec=False`; `size_px < min(width,height)/4`; `count ≥ 1`; brightness in (0,255].
- Disturbances: `gaussian.sigma_levels ≤ 20` (spec "noise σ max 20"; interpreted as grey levels — documented in `docs/CONFIG.md`); `|jitter| ≤ 20 px/frame`, `|platform| ≤ 20 px/frame`; densities in [0,1].
- Tracking: `confirm_hits ≤ confirm_window`; `scan_rate ≤ gimbal.slew_rate`; `association_gate_px ≥ 2 × size_px/2`; **cross-field:** `tracking.reacquire_timeout_s ≤ requirements.reacquisition_max_s`; `tracking.acquire_timeout_s ≤ requirements.acquisition_max_s`; `control.deadband_px < requirements.lock_radius_px`.
- Requirements are **evaluation thresholds only** — the tracker never reads them for behaviour (only validated against).
- `config_hash(cfg)` = SHA-256 of canonical JSON; embedded in every run record.

---

## 4. Migration / Reuse / Delete Map

Principle: nothing survives because it exists. Old code is *reference*, moved to `legacy/` in Phase 0, deleted in Phase 12.

| Existing item | Decision | Reason |
|---|---|---|
| `src/skylock/config.py` | **Rewrite** → `config/` | singletons as default args; chroma/blink/scintillation fields; duplicate spec constants. Keep only PS-spec comments |
| `geometry.py` | **Rewrite** (keep `wrap_deg`, `angular_diff_deg` + tests) | 3D pinhole with satellite pan/tilt convention is unnecessary; use tangent-plane model |
| `gimbal.py` | **Refactor & port** → `simulation/gimbal.py` | accel-limited slew is right; remove `run_gimbal_self_test`, dict state, pan-wrap ±180, initial pan 90; implement `GimbalPlant` |
| `controller.py` | **Rewrite** → `control/` using old PID maths as reference | dict API, coupled to global config; new one takes image-space error |
| `kalman.py` | **Rewrite** → `tracking/kalman.py` | dict API, time-keyed, singleton config; new: matrix form, Joseph update, Mahalanobis gate |
| `state_machine.py` | **Rewrite** | string states, dict I/O, blink-ID dependencies, 10 s coast, GT-shaped `losOccluded` concept |
| `scan_patterns.py` | **Port concept** (raster + spiral) | re-parameterise for 4°×3° FOV, field of regard, local REACQUIRE radius |
| `detector.py` | **Rewrite** → `vision/` | colour/chroma; dict output; per-blob full-frame mask loops (slow) |
| `candidate_tracker.py` | **Rewrite** | blink-history matched filter not in spec; keep nearest-neighbour gating idea |
| `beacon_id.py`, JS `decoys.js`, `beaconId.js` | **Delete** | blink-code ID is out of scope (re-add later as optional discriminator) |
| `disturbances.py` | **Delete/Rewrite** → `simulation/disturbances/` | presets don't match required independent components |
| `tests_python/*` | **Port selectively** → `tests/unit/` | reuse numeric cases for wrap/gimbal/PID/Kalman/spiral; delete the rest |
| JS `src/**`, `electron/`, `vite.config.js`, `package*.json`, `eslint*`, `.prettier*`, `index.html`, `tests/*.js`, `scripts/*.mjs`, `public/assets/*.glb` | **Move to `legacy/` (P0) → delete (P12)** | obsolete architecture; algorithms consulted only as reference |
| `docs/PS_SPEC.md` | **Keep (authoritative)** | matches the target spec |
| `docs/PS_PARAMS.md, METRICS.md, CONFIG.md, BENCHMARK_SCHEMA.md, BASELINE.md, CLEAN_MACHINE_TEST.md` | **Rewrite or delete** | describe JS runtime |
| `docs/figures/benchmark.json`, `benchmark-tables.md`, `report-draft.md`, `user-manual-draft.md` | **Delete** (P0 → `legacy/`) | invalid data / stale |
| `README.md` | **Rewrite (P12)** | stale claims |
| `pyproject.toml` / `uv.lock` | **Modify** | set `testpaths=tests`, entry points, `opencv-python-headless` (not `opencv-python`; the GUI wheel ships Qt plugins that conflict with PySide6 in PyInstaller), PySide6 as `gui` extra so core tests run headless; regenerate lock |

---

## 5. Phased Implementation Plan

Global rules that every Antigravity prompt inherits (repeated in each prompt's DO NOT section):

- Work only inside the listed scope. Do not touch unrelated files. No drive-by refactors.
- No module-level mutable state; no module-level default config instances; components take config in `__init__`.
- Every stateful class has `reset()` returning it to construction state.
- No fake defaults: unmeasurable ⇒ `None` with a `MetricStatus`.
- Ground truth never enters `vision/ tracking/ control/ core/pipeline.py`.
- Run `ruff check src tests`, `pytest -q` before reporting. Report honestly, including failures.
- Do not tune parameters to make benchmark numbers pass.

Phase order (dependency order; kept close to the suggested one): 0 cleanup → 1 config/contracts → 2 world/camera/motion → 3 disturbances → 4 vision → 5 tracker → 6 gimbal/control/closed loop → 7 MP4 → 8 metrics → 9 benchmark → 10 GUI → 11 integration/perf → 12 packaging/docs/final cleanup.

---

### Phase 0: Repository Cleanup + Baseline + Skeleton

#### Objective
Freeze the legacy code for reference, create the empty new package skeleton, tooling and the architecture test harness, with a green (trivial) test suite.

#### Scope
Repo root, `pyproject.toml`, `src/skylock/**` (skeleton only), `tests/`, `legacy/`, `docs/`.

#### Dependencies
None.

#### Implementation Tasks
1. Create `legacy/js/` and move: `src/*.js`, `src/tracking/`, `electron/`, `vite.config.js`, `package.json`, `package-lock.json`, `eslint.config.js`, `.prettierrc`, `.prettierignore`, `index.html`, `tests/*.js`, `scripts/*.mjs`, `public/`. Create `legacy/python/` and move the whole old `src/skylock/*.py` and `tests_python/`. Move `docs/figures`, `docs/report-draft.md`, `docs/user-manual-draft.md`, `docs/BASELINE.md`, `docs/CLEAN_MACHINE_TEST.md`, `docs/PS_PARAMS.md`, `docs/METRICS.md`, `docs/CONFIG.md`, `docs/BENCHMARK_SCHEMA.md` into `legacy/docs/`.
2. Write `legacy/README.md`: "Reference only. Not packaged, linted, or tested. Deleted in Phase 12."
3. Record baseline in `docs/BASELINE_AUDIT.md`: old Python tests result (90 passed, run from `legacy/python` with `PYTHONPATH`), list of moved files, the verified findings table from MASTER_PLAN §0.
4. Create skeleton packages exactly as in MASTER_PLAN §1 (`__init__.py` only; `__version__ = "0.1.0"` in `skylock/__init__.py`). Add `src/skylock/__main__.py` printing version.
5. Update `pyproject.toml`: name `skylock`, `requires-python>=3.12`; deps `numpy>=2.0`, `opencv-python-headless>=4.10`; extras `gui=["pyside6>=6.7"]`, `dev=["pytest>=8","pytest-cov","ruff>=0.8","mypy>=1.10","pyinstaller>=6"]`; `[project.scripts] skylock="skylock.app.main:main"`; `testpaths=["tests"]`; ruff line-length 100, select `E,F,W,I,B,UP,SIM`; exclude `legacy`; mypy `strict` for `skylock.core, skylock.config`, `exclude=legacy`; pytest markers `slow`, `gui`, `perf`.
6. Create `tests/architecture/test_import_boundaries.py` implementing the import table from MASTER_PLAN §1 via `ast` (walk `src/skylock/<pkg>/**.py`, collect `import skylock.x` / `from skylock.x import`), with the table as data. Add `tests/architecture/test_no_global_state.py`: AST-fail on module-level assignments to instances of `@dataclass` config classes or module-level lists/dicts/sets mutated (allow constants named UPPER_CASE holding immutables: tuple, frozenset, str, int, float, `MappingProxyType`).
7. `tests/unit/test_smoke.py`: `import skylock; assert skylock.__version__`.
8. `.gitignore`: add `.venv/, dist/, build/, *.spec` exceptions for `packaging/skylock.spec`, `runs/`, `.mypy_cache/`, `.ruff_cache/`.
9. Copy this plan to `docs/MASTER_PLAN.md`. Keep `docs/PS_SPEC.md` in place.

#### Acceptance Criteria
- `python -m skylock` prints `0.1.0`.
- `pytest -q` passes (smoke + 2 architecture tests); `ruff check src tests` clean.
- `legacy/` contains all moved material; repo root has no `package.json`, `electron/`, `*.js`.
- `git status` (or file listing) shows moves, not deletions of content.

#### Tests
`tests/unit/test_smoke.py`, `tests/architecture/test_import_boundaries.py`, `tests/architecture/test_no_global_state.py`.

#### Files Created
`legacy/README.md`, `docs/BASELINE_AUDIT.md`, `docs/MASTER_PLAN.md`, skeleton `__init__.py` files, `src/skylock/__main__.py`, tests above.

#### Files Modified
`pyproject.toml`, `.gitignore`.

#### Files Deleted
None (moved). Root `uv.lock` deleted and regenerated (`uv lock`) if `uv` is used; otherwise left.

#### Risks
Moving files breaks nothing but old tests need `PYTHONPATH`; opencv wheel change affects local env (use a fresh venv).

#### Antigravity Prompt
```text
You are implementing Phase 0 of the SkyLock Python rebuild.

1. READ FIRST
- docs/MASTER_PLAN.md (if absent, the plan file provided by the user), sections 0, 1, 4, and the "Phase 0" block.
- docs/PS_SPEC.md.

2. CURRENT STATE
Repo is a mixed JS(Three.js/Electron) + partial Python project. Python package src/skylock/ has algorithm modules only (config, geometry, gimbal, kalman, detector, candidate_tracker, state_machine, scan_patterns, controller, disturbances, beacon_id). 90 Python tests in tests_python/ pass. Nothing is wired together.

3. GOAL
Freeze legacy code into legacy/, create the new empty package skeleton, tooling config, and architecture-enforcement tests. No algorithm code is written in this phase.

4. FILES TO INSPECT
pyproject.toml, .gitignore, README.md, src/skylock/*.py (headers only), tests_python/, docs/, package.json.

5. IMPLEMENTATION
a) Run the OLD python tests once first: `PYTHONPATH=src python -m pytest tests_python -q`; record the result.
b) Move (do not rewrite) legacy code:
   - legacy/js/: src/*.js, src/tracking/, electron/, vite.config.js, package.json, package-lock.json, eslint.config.js, .prettierrc, .prettierignore, index.html, tests/*.js, scripts/*.mjs, public/
   - legacy/python/: src/skylock/*.py and tests_python/
   - legacy/docs/: docs/figures, docs/report-draft.md, docs/user-manual-draft.md, docs/BASELINE.md, docs/CLEAN_MACHINE_TEST.md, docs/PS_PARAMS.md, docs/METRICS.md, docs/CONFIG.md, docs/BENCHMARK_SCHEMA.md
   Keep docs/PS_SPEC.md where it is. Write legacy/README.md ("Reference only; not packaged/linted/tested; deleted in Phase 12").
c) Create the skeleton exactly: src/skylock/{app,config,core,vision,tracking,control,simulation,simulation/disturbances,input,metrics,benchmark,ui}/__init__.py (empty docstring), src/skylock/__init__.py with __version__ = "0.1.0", src/skylock/__main__.py printing the version. Create empty dirs tests/{unit,integration,e2e,benchmark,architecture,fixtures}, scripts/, packaging/ (with .gitkeep).
d) Rewrite pyproject.toml: name skylock; requires-python >=3.12; dependencies numpy>=2.0, opencv-python-headless>=4.10; optional-dependencies gui=[pyside6>=6.7], dev=[pytest>=8, pytest-cov, ruff>=0.8, mypy>=1.10, pyinstaller>=6]; [project.scripts] skylock = "skylock.app.main:main"; setuptools src layout (packages.find where=src include skylock*); pytest testpaths=["tests"] with markers slow, gui, perf; ruff line-length 100, lint select E,F,W,I,B,UP,SIM, extend-exclude legacy; mypy strict for skylock.core and skylock.config, exclude legacy.
e) tests/architecture/test_import_boundaries.py: using ast, parse every .py under src/skylock/<package>/ and assert the allowed-import table from MASTER_PLAN section 1 (table stored as a dict in the test). Also assert no skylock module imports skylock.ui except skylock.ui itself and skylock.app.main (lazy import inside function only).
f) tests/architecture/test_no_global_state.py: AST-check that no module in src/skylock has a module-level assignment whose value is a Call to a class ending in "Config", or a list/dict/set display/comprehension (UPPER_CASE names holding tuple/frozenset/str/int/float/MappingProxyType are allowed).
g) tests/unit/test_smoke.py.
h) Write docs/BASELINE_AUDIT.md: old test result, list of moved files, the verified-findings table from MASTER_PLAN section 0.
i) Copy the master plan to docs/MASTER_PLAN.md if not already there. Update .gitignore (.venv, dist, build, runs/, .mypy_cache, .ruff_cache).

6. TESTS
`pip install -e .[dev]` then: `pytest -q` ; `ruff check src tests` ; `python -m skylock`.

7. ACCEPTANCE CRITERIA
- python -m skylock prints 0.1.0
- pytest passes (smoke + 2 architecture tests); ruff clean
- No package.json, electron/, or *.js remain outside legacy/
- legacy/ contains every moved item; nothing was rewritten or deleted (only moved), except uv.lock which you may regenerate with `uv lock` if uv is available

8. DO NOT
- Do not write any tracking/vision/simulation logic.
- Do not delete legacy content; do not edit legacy files.
- Do not add dependencies beyond those listed. Do not use opencv-python (GUI wheel); use opencv-python-headless.
- Do not modify docs/PS_SPEC.md.

9. FINAL REPORT
List: tests run, results, files created, files moved (grouped), files modified, known limitations, remaining work (Phase 1 next).
```

---

### Phase 1: Configuration + Core Data Models + Frame API

#### Objective
Implement the single config model with validation, the core contracts (Frame API, enums, types, protocols), geometry helpers, and RNG derivation.

#### Scope
`src/skylock/config/*`, `src/skylock/core/{types,enums,interfaces,geometry,rng,errors}.py`, `docs/CONFIG.md`.

#### Dependencies
Phase 0.

#### Implementation Tasks
1. `config/models.py`: frozen dataclasses per MASTER_PLAN §3 (`CameraConfig, GimbalConfig, TargetConfig, TargetSetConfig, MotionConfig variants (LineMotion, CircleMotion, Figure8Motion, RandomMotion), DetectionConfig, TrackingConfig, KalmanConfig, SearchConfig, ControlConfig, DisturbanceConfig (+ component configs), InputConfig, RequirementsConfig, SkyLockConfig`). Enums as `StrEnum`. Derived read-only properties (`ifov_h_deg`, `ifov_v_deg`, `frame_period_s`, `px_per_deg`).
2. `config/validation.py`: rules of §3; `ConfigError(violations: list[str])`; `validate_root(cfg)` cross-field checks. `__post_init__` per section calls its own rules; root validation runs in `SkyLockConfig.__post_init__`.
3. `config/io.py`: `to_dict`, `from_dict` (strict: unknown keys raise), `to_json/from_json`, `snapshot(cfg) -> dict`, `config_hash(cfg) -> str`, `override(cfg, **dotted)` (e.g. `override(cfg, {"camera.fps": 60.0})` via `dataclasses.replace`, revalidating).
4. `config/presets.py`: `spec_default() -> SkyLockConfig`; disturbance presets as functions returning `DisturbanceConfig` (`clear`, `haze`, `fog`, `rain`, `low_light`, `spec_max_noise`, `spec_max_jitter`) — pure functions, no module-level instances.
5. `core/enums.py`: `TrackState{SEARCH,ACQUIRE,TRACK,LOST,REACQUIRE}`, `MetricStatus{NOT_RUN,NOT_ACQUIRED,MEASURED,FAILED}`, `Verdict{PASS,FAIL,INDETERMINATE}`, `InputKind{SIMULATION,MP4}`, `ControlMode{AUTO,MANUAL}`.
6. `core/types.py` (frozen, slots): `Pointing(pan_deg, tilt_deg)`; `Frame(image: np.ndarray, index: int, timestamp_s: float, source_id: str, pointing: Pointing|None, meta: Mapping[str, float|str])` — `__post_init__` asserts `image.ndim==2`, `dtype==uint8`, sets `image.flags.writeable=False`; `Detection(cx, cy, area_px, peak, snr, bbox)`; `Candidate(id, cx, cy, age, hits, misses, confirmed, score)`; `TargetEstimate(pan_deg, tilt_deg, pan_rate, tilt_rate, px, py, sigma_deg, from_measurement: bool)`; `ControlIntent(mode: HOLD|TRACK|GOTO, setpoint_pan_deg, setpoint_tilt_deg, image_error_px: (float,float)|None)`; `ControlCommand(pan_rate_deg_s, tilt_rate_deg_s)`; `PipelineOutput(frame_index, timestamp_s, state, estimate|None, detections, selected: Candidate|None, intent, latency_ms)`; `GroundTruthSample(frame_index, timestamp_s, targets: tuple[TargetTruth,...], primary_px: (x,y)|None, primary_visible: bool, boresight_error_px: float|None, pointing: Pointing)`. `GroundTruthSample` lives in `core/types.py` but is documented "metrics-only".
7. `core/interfaces.py`: `Protocol`s `FrameSource` (`open()`, `read() -> Frame|None` (None = end-of-stream), `reset()`, `close()`, properties `width,height,fps,source_id,kind`), `Detector` (`detect(frame, roi=None) -> list[Detection]`, `reset()`), `GimbalPlant` (`command(cmd, dt)`, `pointing`, `reset()`).
8. `core/geometry.py`: `wrap_deg`, `angular_diff_deg`, `pixel_to_angle_offset(px,py,cam)->(dpan,dtilt)`, `angle_offset_to_pixel(...)`, tangent-plane model (small-angle exact enough at 4°; use `tan` for correctness), sign convention: +pan → image right, +tilt → image up; pixel origin top-left; boresight = `(width-1)/2, (height-1)/2`.
9. `core/rng.py`: `derive_rng(seed:int, name:str) -> np.random.Generator` using `SeedSequence(entropy=seed, spawn_key=(zlib.crc32(name),))`.
10. Port numeric test cases for `wrap_deg/angular_diff` from `legacy/python/tests_python/test_geometry.py`.
11. `docs/CONFIG.md`: table of every field, default, valid range, spec reference.

#### Acceptance Criteria
- `spec_default()` builds and validates; `ifov_h_deg == 0.00625`.
- Invalid configs (fov mismatch, slew 11, fps 20, size 4/21, noise 25, jitter 21, reacquire_timeout 1.5, etc.) each raise `ConfigError` naming the field; multiple violations appear in one exception.
- JSON round-trip equality; `config_hash` stable across runs and changes when any field changes.
- `Frame` rejects non-uint8, 3-channel, and is immutable (write raises).
- mypy strict passes on `skylock.core` and `skylock.config`.

#### Tests
`tests/unit/config/test_models.py, test_validation.py, test_io.py, test_presets.py`; `tests/unit/core/test_types.py, test_geometry.py, test_rng.py` (same seed+name → same stream; different names → different; independent of creation order); extend architecture tests.

#### Files Created
As listed in scope + tests.

#### Files Modified
`docs/CONFIG.md` (new), architecture test table (add `config`, `core`).

#### Files Deleted
None.

#### Risks
Over-engineering config; ambiguity of "noise σ ≤ 20 px" (documented as grey levels; keep a single constant in `validation.py` referenced by docs).

#### Antigravity Prompt
```text
You are implementing Phase 1 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 1, 2.2, 3 and the "Phase 1" block; docs/PS_SPEC.md; legacy/python/config.py and legacy/python/geometry.py (reference only).

2. CURRENT STATE
Phase 0 done: empty skeleton packages, tooling, architecture tests, legacy/ folder. No config or contracts exist.

3. GOAL
Implement (a) the single authoritative typed configuration with validation, (b) core contracts: Frame API, enums, types, protocols, geometry, RNG derivation.

4. FILES TO INSPECT
pyproject.toml, tests/architecture/*, legacy/python/config.py, legacy/python/geometry.py, legacy/python/tests_python/test_geometry.py, docs/PS_SPEC.md.

5. IMPLEMENTATION
Create exactly:
- src/skylock/config/{models.py,validation.py,io.py,presets.py}
- src/skylock/core/{enums.py,types.py,interfaces.py,geometry.py,rng.py,errors.py}
Requirements:
a) All configs are `@dataclass(frozen=True, slots=True)`; sections: CameraConfig, GimbalConfig, TargetConfig, TargetSetConfig, LineMotion/CircleMotion/Figure8Motion/RandomMotion, DetectionConfig, KalmanConfig, SearchConfig, TrackingConfig, ControlConfig, DisturbanceConfig with components SaltPepperConfig, GaussianConfig, PoissonConfig, JitterConfig, PlatformConfig, AtmosphereConfig(mode: clear|haze|fog|rain|low_light), BlurConfig, InputConfig, RequirementsConfig, root SkyLockConfig (fields: camera, target, detection, tracking, control, gimbal, disturbances, input, requirements, seed). Defaults per MASTER_PLAN section 3 table. NO module-level default instances anywhere; `presets.spec_default()` is a function.
b) Validation exactly as MASTER_PLAN section 3 "Validation rules". `ConfigError(violations: list[str])` collects ALL violations (do not stop at first). Include the square-pixel check, fps>=30 (unless allow_below_spec_fps), slew 0<default<=max<=10, size 5..20 unless strict_spec=False, gaussian sigma_levels<=20, jitter/platform <=20 px/frame, cross-field tracking-vs-requirements timing rules.
c) io.py: to_dict, from_dict (unknown key => ConfigError), to_json, from_json, snapshot, config_hash (SHA-256 of canonical sorted JSON), override(cfg, {"camera.fps": 60.0}) built on dataclasses.replace and re-validating.
d) core/types.py per MASTER_PLAN Phase 1 task 6: Frame is frozen, image must be 2-D uint8, made read-only (`image.flags.writeable=False`); Frame has NO ground-truth field. GroundTruthSample is defined here with a docstring "METRICS ONLY - never import into vision/tracking/control".
e) core/interfaces.py: typing.Protocol classes FrameSource, Detector, GimbalPlant with the exact members listed in the plan (read() returns None at end of stream).
f) core/geometry.py: wrap_deg, angular_diff_deg, pixel_to_angle_offset, angle_offset_to_pixel using tangent-plane projection; conventions: +pan = image right, +tilt = image up, pixel origin top-left, boresight = ((w-1)/2,(h-1)/2). Port wrap/angdiff numeric cases from the legacy geometry tests.
g) core/rng.py: derive_rng(seed, name) via numpy SeedSequence(entropy=seed, spawn_key=(zlib.crc32(name.encode()),)).
h) docs/CONFIG.md listing every field/default/range/spec reference. State the interpretation of "noise sigma max 20" as grey levels.
i) Extend tests/architecture table entries for config and core.

6. TESTS
Create tests/unit/config/{test_models,test_validation,test_io,test_presets}.py and tests/unit/core/{test_types,test_geometry,test_rng}.py. Cover: default validity; ifov_h==0.00625; each invalid case listed in the plan raises ConfigError naming the field; multi-violation aggregation; JSON round-trip equality; hash stability/sensitivity; Frame immutability and dtype/ndim rejection; geometry round-trip pixel->angle->pixel within 1e-9; RNG determinism and name independence.
Run: `ruff check src tests`, `mypy src/skylock/core src/skylock/config`, `pytest -q`.

7. ACCEPTANCE CRITERIA
All tests pass; ruff and mypy clean; spec_default() valid; no module-level config instances (architecture test passes); CONFIG.md complete.

8. DO NOT
- Do not implement detection/tracking/simulation logic.
- Do not add dependencies. Do not use YAML. Do not read legacy code at import time.
- Do not add ground truth to Frame. Do not create global default config objects.
- Do not modify legacy/ or docs/PS_SPEC.md.

9. FINAL REPORT
Tests run + results, files created, files modified, known limitations (e.g. ambiguous spec interpretations you had to make), remaining work.
```

---

### Phase 2: Virtual Scene, Camera, Targets, Motion Models

#### Objective
Deterministic world model that renders clean (disturbance-free) monochrome frames for any pointing, with four motion models, configurable target shape/size/count, random initial location, visibility windows, and a ground-truth side channel.

#### Scope
`simulation/{motion,targets,camera,ground_truth}.py`, `simulation/source.py` (open-loop, fixed pointing), tests.

#### Dependencies
Phases 0–1.

#### Implementation Tasks
1. **Sky frame:** target positions are angles `(az_deg, el_deg)` in a local tangent plane (no Earth, no orbits). `motion.py`: `Trajectory` ABC with `position(t) -> (az, el)` (pure function of `t` for line/circle/figure8) and `reset()`; `LineTrajectory(start, speed_deg_s, heading_deg)`, `CircleTrajectory(center, radius_deg, period_s, phase_rad)`, `Figure8Trajectory` (lemniscate of Gerono: `x = cx + A sin(ωt)`, `y = cy + B sin(ωt)cos(ωt)`), `RandomTrajectory` (seeded Ornstein–Uhlenbeck velocity within `bounds_deg`, reflecting boundaries, precomputed lazily at fixed 1/120 s steps and cached so `position(t)` is repeatable for any `t`; `reset()` regenerates identically).
2. `targets.py`: `Target` (spec + trajectory + visibility), shapes rendered as float sprites in `[0,1]`: `square, disc, gaussian, cross, custom_mask(np.ndarray)`; `visibility_windows: list[(t0,t1)]` during which the beacon is blanked (occlusion) — the simulation's way to test loss/reacquire; random initial location drawn from `derive_rng(seed,"target.initial")` inside a declared `initial_region` (deg box around boresight); `TargetSet` builds `count` targets with per-target seeds.
3. `camera.py`: `VirtualCamera(cfg.camera, sky background)`; `render(pointing, t, extra_offset_px=(0,0)) -> (image_float, TargetRenderInfo[])`. Projection via `core.geometry`. Sub-pixel sprite placement (bilinear splat) so centroids can be sub-pixel; clip at borders (partially visible targets rendered partially). Baseline background: constant dark level (`background_level`, default 20) + optional static star-field/clutter (seeded, off by default). Output float32 → quantised uint8 only at the end of the pipeline (Phase 3 stack) — for Phase 2 quantise directly.
4. `ground_truth.py`: `build_ground_truth(...) -> GroundTruthSample` (true pixel of each target, in-FOV flag, visibility, boresight error px, pointing).
5. `source.py`: `SimulationSource(cfg, gimbal=None)` implements `FrameSource`; Phase 2 uses a `FixedPointingGimbal`; exposes `read()` (Frame only) and `read_with_truth() -> (Frame, GroundTruthSample)`; deterministic timestamps; `reset()` restores everything including RNG.
6. Motion-parameter guard: a helper `px_per_frame(speed_deg_s, cfg)` used in tests to assert scenarios stay within tracker-feasible speeds.

#### Acceptance Criteria
- Same config+seed ⇒ identical frames (SHA-256 of concatenated frames equal) across two independent `SimulationSource` instances and after `reset()`.
- Default target renders as a ~10×10 px bright region; centroid of rendered sprite within 0.1 px of ground-truth position.
- Straight line: constant velocity to 1e-9; circle: constant radius and period; figure-8: closed curve, crossing at centre; random: bounded and seed-dependent.
- Target outside FOV ⇒ blank frame and `primary_visible=False`.
- Visibility window blanks target and GT reports invisible.
- Configuring count=3 produces 3 distinct blobs.

#### Tests
`tests/unit/simulation/test_motion.py, test_targets.py, test_camera.py, test_source_determinism.py, test_ground_truth.py`.

#### Files Created / Modified / Deleted
Created: modules above + tests. Modified: architecture table. Deleted: none.

#### Risks
Sub-pixel splat accuracy; random-walk determinism when queried non-monotonically (solved by caching).

#### Antigravity Prompt
```text
You are implementing Phase 2 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 1, 2, 3 and "Phase 2"; docs/PS_SPEC.md sections 1,2,4,5; src/skylock/config/*, src/skylock/core/*.

2. CURRENT STATE
Config, core types (Frame, GroundTruthSample, Pointing), Frame API protocols, geometry and RNG helpers exist. No simulation code exists.

3. GOAL
Build the clean (no disturbances yet) virtual world: motion models, targets, monochrome virtual camera, ground-truth side channel, and an open-loop SimulationSource that implements the FrameSource protocol.

4. FILES TO INSPECT
src/skylock/config/models.py, src/skylock/core/{types,interfaces,geometry,rng}.py, legacy/js/src/tracking/beacon.js and virtualCamera.js (reference for sprite/projection ideas only; do NOT port Three.js concepts).

5. IMPLEMENTATION
Create in src/skylock/simulation/: motion.py, targets.py, camera.py, ground_truth.py, source.py (+ a FixedPointingGimbal class inside source.py implementing core.interfaces.GimbalPlant that never moves).
- motion.py: Trajectory ABC {position(t)->(az_deg,el_deg), reset()}; LineTrajectory, CircleTrajectory, Figure8Trajectory (x=cx+A*sin(w t), y=cy+B*sin(w t)*cos(w t)), RandomTrajectory (seeded OU velocity, bounded with reflection, generated lazily on a fixed 1/120 s grid and cached so position(t) is repeatable for any t in any query order). Use core.rng.derive_rng(seed, "motion.<target_index>").
- targets.py: shapes square/disc/gaussian/cross/custom_mask as float32 sprites in [0,1] of size size_px; TargetSet from cfg.target (count, per-target seed, random initial location inside an initial_region box in degrees around boresight, drawn with derive_rng(seed,"target.initial")); visibility_windows list[(t0,t1)] blanking the beacon.
- camera.py: VirtualCamera(cfg.camera) with render(pointing, t, extra_offset_px=(0.0,0.0)) -> (float32 image 0..255, list[TargetRenderInfo(px,py,visible,in_fov)]). Use core.geometry tangent-plane projection, bilinear sub-pixel splatting, partial clipping at borders, constant background_level (default 20; add it to CameraConfig or SimulationConfig if missing - if you must add a config field, do it in config/models.py with validation and update docs/CONFIG.md and tests).
- ground_truth.py: build_ground_truth(...)->GroundTruthSample using true rendered pixel positions.
- source.py: SimulationSource(cfg) implements FrameSource; read() returns Frame; read_with_truth() returns (Frame, GroundTruthSample); timestamps = index/fps; reset() fully restores state incl. RNG streams. Quantise to uint8 with rounding+clip at the end. The Frame it returns must contain NO ground truth; put pointing in Frame.pointing.
Constraints: simulation must not import tracking/vision/control/metrics/ui.

6. TESTS
tests/unit/simulation/{test_motion,test_targets,test_camera,test_source_determinism,test_ground_truth}.py covering: line constant velocity; circle radius/period; figure-8 closed curve & centre crossing; random bounded + seed-sensitive + repeatable for out-of-order queries + reset() identical; 10x10 default sprite; centroid of rendered target within 0.1 px of truth (compute centroid in the test with numpy); off-FOV frame is blank and primary_visible False; visibility window blanks; count=3 gives 3 blobs (cv2.connectedComponents in test); two SimulationSource instances with same seed yield equal SHA-256 over 60 frames; reset() reproduces the same hash.
Run `ruff check src tests`, `mypy src/skylock/core src/skylock/config`, `pytest -q`.

7. ACCEPTANCE CRITERIA
All listed tests pass; architecture tests still pass; determinism hash test passes; no global state.

8. DO NOT
- No noise/jitter/atmosphere (Phase 3). No gimbal dynamics (Phase 6). No detection code.
- Do not modify Frame (no ground truth field). Do not touch legacy/.
- Do not use Python's `random` or `np.random` global state.

9. FINAL REPORT
Tests run/results, files created, files modified (config additions must be listed explicitly), known limitations, remaining work.
```

---

### Phase 3: Sensor / Disturbance Model

#### Objective
Independent, seedable, resettable disturbance components composed into a stack applied inside the simulation.

#### Scope
`simulation/disturbances/*`, wiring in `simulation/source.py`, `simulation/camera.py` (extra offset), tests.

#### Dependencies
Phase 2.

#### Implementation Tasks
1. `base.py`: `Disturbance` ABC: `reset()`, `apply(image: float32, ctx: DisturbanceContext) -> float32` for photometric ones; geometric ones (`jitter`, `platform`) implement `offset_px(frame_index, t) -> (dx, dy)` instead. Each component owns its RNG from `derive_rng(seed, "dist.<name>")` and re-creates it on `reset()`.
2. Components: `SaltPepperNoise(density)`; `GaussianNoise(sigma_levels)`; `PoissonNoise(photon_scale)` (shot noise: `poisson(img*scale)/scale`, with fast path for large λ if performance requires, documented); `CameraJitter(max_px_frame, correlation)` (bounded, per-frame offset, `|dx|,|dy| ≤ max`); `PlatformMotion` (`kind=linear`: constant `velocity_px_frame` vector accumulating per frame, wrapped/clamped by `max_px_frame` on per-frame velocity; optional `sinusoidal`); `Atmosphere(mode, strength)`: clear = identity, haze = contrast compression + additive veil, fog = stronger veil + attenuation + slight blur, rain = seeded streak/dropout overlay + mild attenuation, low_light = gain reduction (signal × g) with unchanged noise floor; `OpticalBlur(sigma_px)` (cv2.GaussianBlur).
3. `stack.py`: `DisturbanceStack(cfg, seed)`; fixed order: **geometric offsets** (jitter+platform → passed to `VirtualCamera.render` as `extra_offset_px` so GT reflects it) → render → atmosphere → blur → poisson → gaussian → salt&pepper → quantise. Every component independently enabled; disabled ⇒ zero cost and zero RNG consumption.
4. `SimulationSource` uses the stack; `GroundTruthSample` includes applied `(dx,dy)` disturbance offset.
5. Clean reset: `stack.reset()` restores every component; verify no cross-component RNG coupling (enabling/disabling one component must not change another's stream).
6. Document each model's equations and units in `docs/DISTURBANCES.md`.

#### Acceptance Criteria
- Statistical: Gaussian σ measured on blank frame within 5 % of configured; S&P fraction of extremes within 10 % of density; Poisson variance ≈ mean·(1/scale); jitter never exceeds ±20 px/frame; platform linear drift equals configured velocity.
- Enabling only jitter produces identical noise-free pixels as clean render shifted by the offset.
- Toggling any one component leaves other components' output bit-identical (stream independence).
- Same seed ⇒ identical frames; `reset()` ⇒ identical again.
- Atmosphere modes ordered: contrast(clear) > contrast(haze) > contrast(fog) on a reference frame; low_light peak < clear peak.

#### Tests
`tests/unit/simulation/disturbances/test_{noise,jitter,platform,atmosphere,blur,stack,independence,reset}.py`.

#### Files Created / Modified / Deleted
Created: modules + `docs/DISTURBANCES.md` + tests. Modified: `simulation/source.py`, `simulation/camera.py`. Deleted: none.

#### Risks
Poisson cost at 640×480 (budget ≤ 6 ms — measure); atmosphere realism is heuristic — document it as such.

#### Antigravity Prompt
```text
You are implementing Phase 3 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 2, 3 and "Phase 3"; docs/PS_SPEC.md section 6; src/skylock/simulation/*; src/skylock/config/models.py (DisturbanceConfig).

2. CURRENT STATE
Clean SimulationSource renders deterministic mono frames + GroundTruthSample. No noise, jitter, platform motion, atmosphere or blur.

3. GOAL
Implement independent, seeded, resettable disturbance components and a DisturbanceStack wired into SimulationSource.

4. FILES TO INSPECT
src/skylock/simulation/{camera,source,ground_truth}.py, src/skylock/core/rng.py, legacy/python/disturbances.py and legacy/js/src/tracking/disturbances.js (reference for ideas only).

5. IMPLEMENTATION
Create src/skylock/simulation/disturbances/{base,noise,jitter,platform,atmosphere,blur,stack}.py.
- base.py: `Disturbance` ABC with reset(). Photometric components implement apply(image_f32, ctx)->image_f32. Geometric components (CameraJitter, PlatformMotion) implement offset_px(frame_index, t)->(dx,dy).
- Each component creates its RNG in __init__/reset via derive_rng(seed, f"dist.{name}"); reset() re-creates it. Disabled components consume no RNG and do no work.
- SaltPepperNoise(density); GaussianNoise(sigma_levels); PoissonNoise(photon_scale) (poisson(img*scale)/scale; if cost >6 ms at 640x480 use a documented normal approximation when lambda>50); CameraJitter(max_px_frame, correlation in [0,1)) with hard clip |dx|,|dy|<=max_px_frame; PlatformMotion(kind="linear", velocity_px_frame=(vx,vy), max_px_frame) - per-frame velocity magnitude clipped to max_px_frame, position accumulates; Atmosphere(mode clear|haze|fog|rain|low_light, strength) implemented as: haze= contrast compression toward background + additive veil; fog = stronger veil + attenuation + sigma~1 blur; rain = seeded streaks + mild attenuation; low_light = signal gain g<1 with noise floor unchanged; OpticalBlur(sigma_px) via cv2.GaussianBlur.
- stack.py: DisturbanceStack(cfg.disturbances, seed) with fixed order: geometric offsets -> pass to VirtualCamera.render(extra_offset_px) so ground truth reflects the shift -> atmosphere -> blur -> poisson -> gaussian -> salt&pepper -> round/clip to uint8. reset() resets all components.
- Modify SimulationSource to use the stack; GroundTruthSample must record the applied (dx,dy) offset and post-disturbance true pixel.
- Write docs/DISTURBANCES.md (equations, units, order, seeds).

6. TESTS
tests/unit/simulation/disturbances/: test_noise (gaussian sigma within 5%, S&P extreme fraction within 10% of density, poisson var~mean/scale), test_jitter (|offset|<=20 always for max=20, seed determinism), test_platform (linear drift equals configured velocity, clipping), test_atmosphere (contrast ordering clear>haze>fog, low_light peak<clear peak), test_blur (peak decreases, energy preserved within 2%), test_stack (order, disabled=no-op bit-identical to clean), test_independence (toggle one component; others' pixels bit-identical when isolated - test by isolating each component's own output), test_reset (same seed -> same frames; reset() -> same again).
Run `ruff check src tests`, `pytest -q`. Report measured per-frame times of each component at 640x480.

7. ACCEPTANCE CRITERIA
All tests pass; spec limits (sigma<=20, jitter/platform<=20 px/frame) enforced both by config validation and by runtime clipping; determinism proven by hash tests.

8. DO NOT
- Do not use global RNG. Do not change Frame or the tracker-facing API. Do not add detection code. Do not change spec limits. Do not add scintillation/hot-pixel/frame-drop features (out of spec).

9. FINAL REPORT
Tests + results, per-component timing, files created/modified, known limitations, remaining work.
```

---

### Phase 4: Vision Detection + Centroid + Candidate Association

#### Objective
Classical CV detector for 5–20 px monochrome beacons robust to the Phase 3 disturbances, with sub-pixel centroids, plus candidate association (no Kalman yet).

#### Scope
`vision/{preprocess,detector,centroid}.py`, `tracking/candidate_tracker.py`, `core/types.py` (if fields missing), tests, synthetic-frame test helpers.

#### Dependencies
Phases 1–3.

#### Implementation Tasks
1. `preprocess.py`: optional median 3×3 (kills salt-and-pepper without erasing ≥5 px blobs — verify), Gaussian σ smoothing, background estimate via large box filter or morphological open (`kernel ≈ 3×max_size`), background-subtracted image.
2. Noise estimate: robust σ = 1.4826·MAD of background-subtracted ROI; threshold `T = max(abs_min_threshold, k·σ)`.
3. `detector.py`: `ClassicalBlobDetector(cfg.detection)`: `detect(frame, roi=None)`: threshold → `cv2.connectedComponentsWithStats(connectivity=8)` → filter by area `[min,max]`, bbox aspect (≤3), fill ratio (≥0.4) → per-blob intensity-weighted centroid computed **on the bbox crop only** (no full-frame mask per blob) → `Detection(cx, cy, area, peak, snr, bbox)` sorted by `snr`. ROI support (full-frame coordinates returned). `latency` not measured here.
4. `centroid.py`: pure function `weighted_centroid(crop, origin, background)`.
5. `candidate_tracker.py` (association only): `CandidateTracker(cfg.tracking)`: nearest-neighbour association with gating around each candidate's last/predicted position (`predicted_px` optional argument — provided by Phase 5), gate `association_gate_px + miss_count*growth`; M-of-N confirmation (`confirm_hits` within `confirm_window`); candidate `id` monotonic; drop after `lost_after_misses`; `reset()`.
6. Test helper `tests/helpers/synthetic.py`: `make_frame(size, positions, blob_size, level, noise...)` independent of the simulator (so detector tests don't depend on simulation).
7. Optional ML detector: define nothing now; docs note "YOLO deferred, must implement `Detector` protocol".

#### Acceptance Criteria
- Clean 10×10 blob: centroid error < 0.15 px; sizes 5,10,20 all detected.
- With Gaussian σ=20, S&P density 2 %, Poisson on: detection rate ≥ 95 % and false-positive count per frame ≤ 0.1 on 300 seeded frames (measured; report actual numbers).
- Low-light and haze presets: report detection rate; no threshold changes to force a pass — if <90 % record it in report as a known limitation.
- Three separated blobs → three detections; two blobs merged when touching → one.
- Empty/uniform frames → `[]`, no exceptions; ROI results equal full-frame results inside ROI.
- 640×480 full-frame detect median latency ≤ 6 ms (report; `perf` marker test soft-asserts ≤ 15 ms).
- Association keeps IDs stable for a moving blob (≤ 20 px/frame) and confirms after 3 hits; two crossing blobs do not swap IDs when separated by > gate.

#### Tests
`tests/unit/vision/test_detector.py, test_centroid.py, test_preprocess.py`; `tests/unit/tracking/test_candidate_tracker.py`; `tests/integration/test_sim_to_detector.py` (SimulationSource→detector, GT used only inside the test to score); `tests/perf/test_detector_latency.py` (`perf`).

#### Files Created / Modified / Deleted
Created: modules + tests + helper. Modified: `core/types.py` only if a needed field is missing (list it). Deleted: none.

#### Risks
Threshold tuning drift → tests must use configured defaults; merged blobs under blur; rain streaks as false candidates.

#### Antigravity Prompt
```text
You are implementing Phase 4 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 2.2, 3 and "Phase 4"; docs/PS_SPEC.md sections 4 and 6; src/skylock/core/{types,interfaces}.py; src/skylock/config/models.py (DetectionConfig, TrackingConfig).

2. CURRENT STATE
SimulationSource produces mono uint8 Frames with disturbances and ground truth (side channel). No vision/tracking code exists.

3. GOAL
Implement a classical-CV blob detector for 5-20 px monochrome beacons, sub-pixel centroiding, and a candidate association module (nearest-neighbour + M-of-N confirmation). No Kalman, no state machine yet.

4. FILES TO INSPECT
legacy/python/detector.py and legacy/python/candidate_tracker.py (REFERENCE ONLY - they are colour/dict based; do not copy structure), src/skylock/simulation/source.py.

5. IMPLEMENTATION
Create src/skylock/vision/{preprocess.py,detector.py,centroid.py} and src/skylock/tracking/candidate_tracker.py, tests/helpers/synthetic.py.
- Detector input is `Frame` (2-D uint8). Pipeline: optional 3x3 median (config.median_filter) -> Gaussian blur (config.blur_sigma) -> background estimate (box filter with kernel >= 3x max target size, computed on the ROI if given) -> subtract -> robust sigma = 1.4826*MAD -> threshold T = max(abs_min_threshold, threshold_k_sigma*sigma) -> cv2.connectedComponentsWithStats(connectivity=8) -> filters (area in [min_area_px,max_area_px], bbox aspect <=3, fill ratio >=0.4) -> intensity-weighted centroid computed ONLY on each blob's bbox crop (never a full-frame mask per blob) -> list[Detection] sorted by snr desc, truncated to max_blobs.
- `detect(frame, roi=None)` returns coordinates in full-frame pixels. reset() exists (stateless, no-op). Implements core.interfaces.Detector.
- CandidateTracker: update(detections, frame_index, predicted_px=None) -> list[Candidate]; nearest-neighbour association (greedy by distance, one-to-one) with gate association_gate_px + growth per miss; M-of-N confirmation (confirm_hits within confirm_window); monotonic ids; drop after lost_after_misses; reset() restores ids and history.
- tests/helpers/synthetic.py: make_frame(size, blobs, ...) independent of simulation.
Constraints: vision/ and tracking/ must not import skylock.simulation or skylock.metrics (architecture test must pass). No dict-based APIs; use core.types.Detection/Candidate.

6. TESTS
Unit: centroid error <0.15 px for sizes 5,10,20; three separate blobs -> 3 detections; touching blobs -> 1; empty/uniform frame -> []; ROI result equals full-frame result inside ROI; S&P defeated by median (5x5 blob survives); association ID stability for a blob moving 15 px/frame; confirmation after 3 hits; miss handling and drop; reset.
Integration `tests/integration/test_sim_to_detector.py`: 300 seeded frames of SimulationSource with gaussian sigma 20 + S&P 2% + poisson; use ground truth ONLY inside the test to score. Report actual detection rate and false positives/frame. Also run haze, fog, rain, low_light and report rates. Do NOT change defaults or thresholds to make numbers look better; if a scenario is below 90% detection, record it in the report.
Perf test (marker perf): median detect() latency on 640x480 full frame; report the number.
Run `ruff check src tests`, `mypy src/skylock/core src/skylock/config`, `pytest -q`, `pytest -q -m perf`.

7. ACCEPTANCE CRITERIA
Clean-frame criteria pass; disturbed-frame detection >=95% and FP <=0.1/frame for the gaussian20+S&P2%+poisson case (or clearly reported failure with analysis); association tests pass; architecture tests pass; median full-frame latency reported (target <=6 ms).

8. DO NOT
- Do not use chroma/colour detection. Do not import ground truth. Do not add YOLO/ML. Do not add Kalman/state machine. Do not tune parameters to hit pass numbers. Do not modify simulation code except a bug fix you list in the report.

9. FINAL REPORT
Tests + results, measured detection rates per disturbance case, latency numbers, files created/modified, known limitations, remaining work.
```

---

### Phase 5: Kalman + Tracking State Machine + Reacquisition + Pipeline

#### Objective
Complete image-only tracker: Kalman filter, five-state machine (SEARCH/ACQUIRE/TRACK/LOST/REACQUIRE), local reacquisition with a hard deadline, and `TrackingPipeline` (Frame → `PipelineOutput`), testable with no simulator and no gimbal.

#### Scope
`tracking/{kalman,search_patterns,state_machine,tracker}.py`, `core/pipeline.py`, tests.

#### Dependencies
Phases 1, 4.

#### Implementation Tasks
1. `kalman.py`: 4-state constant-velocity filter `[pan, tilt, vpan, vtilt]` in sky-frame degrees; `init(z, t)`, `predict(t)`, `update(z, t, R)`, `mahalanobis(z)`, `state`, `position_sigma_deg`, `reset()`. Discrete white-noise acceleration Q; Joseph-form covariance update; `dt` from timestamps; NumPy only. `R` derived from `r_meas_px × IFOV`.
2. `search_patterns.py`: `RasterScan(field_of_regard_deg, fov, overlap, scan_rate)` → `setpoint(t_since_start) -> (pan, tilt)` (boustrophedon, row spacing = `fov_v·(1−overlap)`); `LocalSpiral(center, max_radius_deg, spacing = fov_v·(1−overlap), rate)` for REACQUIRE. Both pure functions of elapsed time; `reset()`.
3. `tracker.py`: `Tracker` orchestrates: `CandidateTracker` → select measurement (best gated candidate, nearest to Kalman prediction in TRACK/LOST/REACQUIRE; highest confirmed-score in SEARCH/ACQUIRE) → Kalman → `StateMachine`. Converts detection pixel → sky angle using `frame.pointing or Pointing(0,0)` and `core.geometry`. Uses ROI (`roi_margin_px` around predicted pixel) in TRACK/LOST for speed; full frame in SEARCH/ACQUIRE/REACQUIRE-fallback.
4. `state_machine.py` (`StateMachine(cfg.tracking, cfg.search)`), transitions with explicit reasons and an event log (`StateEvent(t, from, to, reason)`):
   - SEARCH → ACQUIRE: ≥1 candidate above `snr_min`.
   - ACQUIRE → TRACK: candidate confirmed (M-of-N); ACQUIRE → SEARCH: `acquire_timeout_s` without confirmation.
   - TRACK → LOST: `lost_after_misses` consecutive frames without a gated measurement.
   - LOST: coast on Kalman prediction; gated measurement → TRACK; after `coast_max_s` → REACQUIRE (spiral centre = predicted position at that time).
   - REACQUIRE: `LocalSpiral` about centre, gate widened by covariance growth; gated/confirmed detection → ACQUIRE→TRACK path (single confirm via ACQUIRE for false-lock protection); if elapsed > `reacquire_timeout_s` → SEARCH with Kalman reset.
   - No input beyond detections/time/pointing; no reference to simulation concepts (no "occlusion" flag).
5. `ControlIntent` from state: SEARCH → `GOTO(raster setpoint)`; ACQUIRE/TRACK → `TRACK(image_error_px)`; LOST → `TRACK` toward predicted position with feed-forward, or `HOLD`; REACQUIRE → `GOTO(spiral setpoint)`.
6. `core/pipeline.py`: `TrackingPipeline(cfg)`: `process(frame) -> PipelineOutput` (measures `latency_ms` with `perf_counter` around detector+tracker only), `reset()`. Constructs detector via `Detector` protocol (injectable). Does not know about sources, gimbals or metrics.
7. Port numeric cases from legacy Kalman/state-machine tests where semantics still apply.

#### Acceptance Criteria
- Kalman: converges on constant-velocity synthetic track (position RMS error < 0.3 px-equivalent after 1 s); NIS mean within [0.5, 2.0]×dof over 500 steps; handles irregular `dt`; `reset()` clears covariance.
- State machine visits all five states under a scripted detection sequence; transition reasons logged; REACQUIRE → SEARCH fires at exactly `reacquire_timeout_s ± 1 frame`.
- Synthetic-frame pipeline (no simulator): target appears → TRACK within `acquire` timing; blank for 8 frames → LOST; reappears near prediction within coast → TRACK; reappears in spiral radius after coast → REACQUIRE→TRACK; never reappears → SEARCH.
- `TrackingPipeline` runs with `pointing=None` (MP4-style) and with pointing telemetry.
- Architecture tests pass (no simulation import in `tracking/` or `core/pipeline.py`).

#### Tests
`tests/unit/tracking/test_kalman.py, test_state_machine.py, test_search_patterns.py, test_tracker.py`; `tests/integration/test_synthetic_pipeline.py` (uses `tests/helpers/synthetic.py`, no sim); `tests/integration/test_sim_to_tracker_open_loop.py` (fixed pointing, moving target in FOV).

#### Files Created / Modified / Deleted
Created: modules + tests. Modified: `core/types.py` (only for `StateEvent` if absent), architecture table. Deleted: none.

#### Risks
Gating vs. ±20 px/frame jitter (0.125°) — gate must exceed jitter without swallowing distractors; ACQUIRE confirmation vs 2 s acquisition budget; Kalman divergence after long coast.

#### Antigravity Prompt
```text
You are implementing Phase 5 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 2, 3 and "Phase 5"; docs/PS_SPEC.md section 7; src/skylock/core/*; src/skylock/vision/*; src/skylock/tracking/candidate_tracker.py; src/skylock/config/models.py.

2. CURRENT STATE
Detector and candidate association exist. No Kalman, state machine, search patterns, tracker or pipeline.

3. GOAL
Implement the full image-only tracker and TrackingPipeline, testable without simulator or gimbal.

4. FILES TO INSPECT
legacy/python/{kalman,state_machine,scan_patterns}.py and legacy/python/tests_python/{test_kalman,test_state_machine,test_scan_patterns}.py (REFERENCE for maths/numeric cases only; the legacy APIs are dict/string-based and must NOT be preserved). legacy/js/src/tracking/stateMachine.js (note: its LOST/REACQUIRE logic used a ground-truth `losOccluded` flag and a 10 s coast - do NOT reproduce either).

5. IMPLEMENTATION
Create src/skylock/tracking/{kalman.py,search_patterns.py,state_machine.py,tracker.py}, src/skylock/core/pipeline.py.
- KalmanFilter: state [pan,tilt,vpan,vtilt] (sky-frame degrees); init(z,t), predict(t), update(z,t,R), mahalanobis(z), reset(); discrete white-noise-acceleration Q from cfg.kalman.q_accel_deg_s2; Joseph-form update; NumPy only; dt from timestamps (support irregular dt, dt<=0 guard).
- search_patterns: RasterScan(field_of_regard, fov, overlap, scan_rate) boustrophedon; LocalSpiral(center, max_radius, spacing=fov_v*(1-overlap), rate). Pure functions of elapsed time.
- StateMachine(cfg.tracking, cfg.search) with enum TrackState, transitions:
  SEARCH->ACQUIRE on >=1 candidate above min snr; ACQUIRE->TRACK on M-of-N confirmation; ACQUIRE->SEARCH on acquire_timeout_s; TRACK->LOST after lost_after_misses consecutive frames without gated measurement; LOST->TRACK on gated measurement; LOST->REACQUIRE after coast_max_s; REACQUIRE->ACQUIRE(->TRACK) on detection; REACQUIRE->SEARCH when elapsed>reacquire_timeout_s (reset Kalman). Log StateEvent(t, from, to, reason) for every transition. No ground-truth or "occlusion" input of any kind; inputs are only detections/candidates, time, pointing.
- Tracker: converts pixel->sky angle using frame.pointing or Pointing(0,0) when None; selects measurement (SEARCH/ACQUIRE: best confirmed/snr; TRACK/LOST/REACQUIRE: nearest to Kalman prediction inside gate); uses ROI (roi_margin_px around predicted pixel) in TRACK/LOST, full frame otherwise; outputs TargetEstimate and ControlIntent (SEARCH: GOTO raster; ACQUIRE/TRACK: TRACK with image_error_px from estimate vs boresight; LOST: TRACK toward prediction; REACQUIRE: GOTO spiral).
- TrackingPipeline(cfg, detector=None): process(frame)->PipelineOutput with latency_ms measured by perf_counter around detector+tracker only; reset() resets detector, candidates, Kalman, state machine and event log. Detector injectable via core.interfaces.Detector.
Constraints: tracking/ and core/pipeline.py must not import skylock.simulation, skylock.metrics, skylock.input, skylock.ui, and must not reference GroundTruthSample.

6. TESTS
Unit: Kalman convergence on constant-velocity track (position RMS < 0.3 px-equivalent after 1 s), NIS mean in [0.5,2.0]*dof over 500 steps, irregular dt, reset; state machine scripted sequences hitting all five states, reasons logged, REACQUIRE->SEARCH at reacquire_timeout_s +/- one frame period; search-pattern coverage (raster rows spaced fov_v*(1-overlap); spiral stays within max_radius); tracker measurement selection and ROI use.
Integration (no simulator): tests/integration/test_synthetic_pipeline.py using tests/helpers/synthetic.py: appear->TRACK; 8 blank frames->LOST; reappear near prediction->TRACK; reappear after coast inside spiral->REACQUIRE->TRACK; never reappear->SEARCH. Also run with pointing=None.
Integration (sim, open loop, fixed pointing): moving target inside FOV reaches TRACK; report state timeline.
Run `ruff check src tests`, `mypy src/skylock/core src/skylock/config`, `pytest -q`.

7. ACCEPTANCE CRITERIA
All listed tests pass; timing of REACQUIRE->SEARCH matches config; pipeline works with and without pointing telemetry; architecture tests pass.

8. DO NOT
- Do not implement PID/gimbal/closed loop (Phase 6). Do not add metrics. Do not import ground truth or simulation. Do not hardcode 1 s / 2 s / 10 px requirement values inside tracker code (use cfg.tracking fields). Do not keep dict-based APIs. Do not tune parameters to force pass.

9. FINAL REPORT
Tests + results, state timelines from the integration tests, files created/modified, known limitations, remaining work.
```

---

### Phase 6: Virtual Gimbal + PID Closed Loop

#### Objective
Slew-limited virtual gimbal, PID pointing controller consuming only estimates/intents, and `Session` closing the loop sim → frame → pipeline → controller → gimbal → next frame.

#### Scope
`simulation/gimbal.py`, `control/{pid,controller}.py`, `app/session.py`, `app/factory.py`, `simulation/source.py` (gimbal integration), tests.

#### Dependencies
Phases 2, 3, 5.

#### Implementation Tasks
1. `simulation/gimbal.py`: `VirtualGimbal(cfg.gimbal)` implements `GimbalPlant`: rate-commanded and position-commanded modes; velocity limited to `slew_rate` (config; hard ceiling `max_slew_rate ≤ 10`), acceleration limit, joint limits (clamp + `at_limit` flag), integrates `substeps` per frame; `pointing` at exposure = value at frame start; `reset()`.
2. `control/pid.py`: `PID(kp, ki, kd, d_alpha, i_clamp)` with derivative-on-measurement low-pass, anti-windup (clamp + conditional integration), `reset()`.
3. `control/controller.py`: `PointingController(cfg.control, camera cfg)`: `step(intent, estimate, dt) -> ControlCommand`; mode `TRACK`: image-space error px → angle error via IFOV → PID + feed-forward of estimated target angular velocity → rate command clipped to slew; `GOTO`: P-controller toward setpoint using gimbal pointing telemetry from the frame; `HOLD`: zero rate. `AUTO/MANUAL`: MANUAL accepts externally set rate commands (for GUI) and ignores the intent. Deadband `< lock_radius`.
4. `app/session.py`: `Session(cfg)`: builds source, pipeline, controller, gimbal, metrics hook (interface only; real collector in Phase 8): `step() -> StepResult(frame, output, command, truth|None)` implementing: read frame (with truth) → `pipeline.process(frame)` → `controller.step(...)` → `gimbal.command(...)` applied with `latency_frames` delay (sim only) → return. `run(max_frames|duration)`, `reset()`. For MP4 sources (Phase 7) the command is computed and returned but not applied (`source.kind` check via protocol property).
5. `app/factory.py`: `build_session(cfg)`, `build_pipeline(cfg)` — the only place that wires concrete classes.
6. Update `SimulationSource` to accept a `GimbalPlant` and advance it each frame.
7. Port PID/gimbal numeric cases from legacy tests (step response, limit clamp, accel limit).

#### Acceptance Criteria
- Gimbal never exceeds `slew_rate` (property test over random commands) nor accel limit; limits clamp; camera cannot snap (max pointing change per frame ≤ `slew·dt + ε`).
- PID step response on the gimbal+camera plant: settles within lock radius, overshoot < 30 %; anti-windup test with saturation shows bounded integral.
- Closed loop (line motion, 0.5°/s, clean): SEARCH→…→TRACK, then camera boresight error (measured in the test with GT) stays ≤ 10 px RMS after lock.
- Controller signature accepts no ground-truth type (test via `inspect.signature` + annotations).
- `Session.reset()` then re-run ⇒ identical PipelineOutput sequence.

#### Tests
`tests/unit/simulation/test_gimbal.py`, `tests/unit/control/test_pid.py, test_controller.py`, `tests/integration/test_closed_loop.py`, `tests/integration/test_session_reset.py`.

#### Files Created / Modified / Deleted
Created: modules + tests. Modified: `simulation/source.py`, architecture table. Deleted: none.

#### Risks
Loop stability with 1-frame latency and 26 px/frame slew; PID gains need principled derivation (document design, do not hand-tune to pass).

#### Antigravity Prompt
```text
You are implementing Phase 6 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 2, 2.3, 3 and "Phase 6"; src/skylock/core/{types,interfaces,pipeline}.py; src/skylock/simulation/source.py; src/skylock/tracking/tracker.py.

2. CURRENT STATE
SimulationSource (fixed pointing), disturbance stack, detector, tracker, TrackingPipeline exist. No gimbal dynamics, PID, controller or Session.

3. GOAL
Implement a slew-limited VirtualGimbal, PID PointingController, and Session that closes the loop with no ground truth reaching the controller.

4. FILES TO INSPECT
legacy/python/gimbal.py, legacy/python/controller.py, legacy/python/tests_python/{test_gimbal,test_controller}.py (reference for slew/accel and PID maths; drop the self-test function, dict state, pan wrap and initial pan 90).

5. IMPLEMENTATION
- src/skylock/simulation/gimbal.py: VirtualGimbal(cfg.gimbal) implements GimbalPlant. Rate and position command modes; |velocity| <= cfg.slew_rate_deg_s; acceleration <= cfg.accel_deg_s2; joint limits clamp with at_limit flags; `substeps` integration per frame; `pointing` property returns Pointing; reset() restores initial pointing/velocity.
- src/skylock/control/pid.py: PID(kp,ki,kd,d_alpha,i_clamp) with derivative-on-measurement filter, clamp + conditional-integration anti-windup, reset().
- src/skylock/control/controller.py: PointingController(cfg.control, cfg.camera). step(intent: ControlIntent, estimate: TargetEstimate|None, pointing: Pointing|None, dt) -> ControlCommand. TRACK: image_error_px * IFOV -> PID + feed-forward of estimate angular velocity -> rate clipped to slew; GOTO: proportional to (setpoint - pointing); HOLD: zeros. MANUAL mode: returns externally supplied rates (set_manual_rate) and ignores intent. deadband_px config. The controller must not accept or import GroundTruthSample.
- src/skylock/app/session.py: Session(cfg) with step()->StepResult(frame, output, command, truth|None), run(frames|seconds), reset(). Order per step: read frame (sim: with truth) -> pipeline.process(frame) -> controller.step(output.intent, output.estimate, frame.pointing, dt) -> apply command to gimbal ONLY if source.kind==SIMULATION, delayed by cfg.control.latency_frames. StepResult.truth is passed through untouched to callers (metrics) and never to pipeline/controller.
- src/skylock/app/factory.py: build_session(cfg), build_pipeline(cfg); only file that instantiates concrete component classes.
- Update SimulationSource to take a GimbalPlant and advance it every frame.
- Write short docs/CONTROL_DESIGN.md explaining how the PID gains were derived (plant = integrator with 1-frame delay; pick gains from a stability margin calculation) - do NOT hand-tune against test results.

6. TESTS
tests/unit/simulation/test_gimbal.py: random-command property test (velocity<=slew, accel<=limit), limit clamp, no-snap (per-frame pointing change <= slew*dt + eps), reset.
tests/unit/control/{test_pid,test_controller}.py: step response, anti-windup bounded integral, deadband, MANUAL override, HOLD, GOTO convergence; annotation test proving no ground-truth type in controller signatures.
tests/integration/test_closed_loop.py: clean scene, line target 0.5 deg/s starting inside FOV: reaches TRACK; after lock boresight error (computed in the test from GroundTruthSample) <=10 px RMS; also a case with circular motion.
tests/integration/test_session_reset.py: run 200 frames, reset(), rerun -> identical PipelineOutput sequence (state, estimate, intent).
Run `ruff check src tests`, `mypy src/skylock/core src/skylock/config`, `pytest -q`.

7. ACCEPTANCE CRITERIA
All tests pass; slew/accel limits proven; camera never snaps; closed-loop lock achieved in the clean scenarios; determinism after reset; architecture tests pass.

8. DO NOT
- Do not exceed 10 deg/s anywhere; do not add instant-snap methods (no `snap_to`). Do not let the controller read simulation objects. Do not add metrics collection or GUI. Do not hand-tune gains to pass tests.

9. FINAL REPORT
Tests + results, design note summary of gains, files created/modified, known limitations, remaining work.
```

---

### Phase 7: MP4 Input Through the Same Frame API

#### Objective
`Mp4Source` produces the same `Frame` type; the identical pipeline processes it; end-of-stream handled explicitly.

#### Scope
`input/{video,sources}.py`, `app/factory.py`, `scripts/gen_test_video.py`, tests.

#### Dependencies
Phases 1, 5, 6.

#### Implementation Tasks
1. `Mp4Source(cfg.input)` implements `FrameSource`: `cv2.VideoCapture`; validates path/open; reads native FPS (`CAP_PROP_FPS`; if ≤0 or NaN → `SourceError`, no silent 30 default unless `input.fps_override` set); converts BGR→gray (`cv2.cvtColor`, or luminance) → uint8 2-D; timestamps `index/fps` (deterministic, not decode time); `pointing=None`; `read()` returns `None` at end of stream and `frames_decoded`, `frames_expected` (may be `None` if container lacks count); `reset()` seeks to frame 0; `close()`; context manager.
2. Resolution: native size is kept (no resize). The pipeline's angle conversion for MP4 uses `input.mp4_assumed_fov_h_deg` and the video size to build an *effective camera* (IFOV) — constructed in `factory`, never by mutating the global config; detection params defined in pixels remain valid.
3. `factory.build_session` with `InputKind.MP4`: no gimbal; commands computed/logged but not applied; `truth=None`.
4. `scripts/gen_test_video.py`: renders a deterministic MP4 (`mp4v`) using `SimulationSource` (Session-free) with noise, for tests; writes `tests/fixtures/` at test time via `tmp_path` (do not commit binaries > 1 MB).
5. Optional evaluation sidecar: `metrics`-side `GroundTruthSidecar` loader (CSV `frame,x,y,visible`) — implemented in Phase 8, **not** in `input/`.

#### Acceptance Criteria
- Same decoded frame array through `Mp4Source` vs a direct `Frame` built from it produces identical `PipelineOutput` (state/estimate) — proves single pipeline.
- Frame count equals container count; timestamps strictly increasing at 1/fps; last `read()` → `None`; further reads keep returning `None`; `reset()` replays identically.
- Missing/corrupt file → `SourceError` with clear message (no partial run).
- Video rendered from the simulator reaches TRACK on the beacon in the pipeline (fixed camera; target moving in view).
- Grayscale conversion documented and tested with a known colour patch.

#### Tests
`tests/unit/input/test_video.py`, `tests/integration/test_mp4_pipeline.py` (`slow` if > 5 s), guarded by `pytest.skip` if `cv2.VideoWriter` cannot open `mp4v` (report which).

#### Files Created / Modified / Deleted
Created: `input/video.py`, `input/sources.py`, `scripts/gen_test_video.py`, tests. Modified: `app/factory.py`, `core/errors.py` (`SourceError`). Deleted: none.

#### Risks
Codec availability in headless OpenCV wheels; VFR videos (timestamps assume CFR — warn if `CAP_PROP_POS_MSEC` deviates > 20 %).

#### Antigravity Prompt
```text
You are implementing Phase 7 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 2 and "Phase 7"; src/skylock/core/{types,interfaces,pipeline}.py; src/skylock/app/{session,factory}.py; docs/PS_SPEC.md section 8.

2. CURRENT STATE
SimulationSource -> Session closed loop works. No video input exists.

3. GOAL
Add Mp4Source implementing FrameSource so MP4 frames go through the SAME TrackingPipeline, with explicit end-of-stream and error handling.

4. FILES TO INSPECT
src/skylock/core/interfaces.py (FrameSource), src/skylock/app/factory.py, src/skylock/simulation/source.py.

5. IMPLEMENTATION
- src/skylock/input/video.py: Mp4Source(cfg.input) using cv2.VideoCapture. open() validates file exists and opens, else raise SourceError. fps from CAP_PROP_FPS; if <=0/NaN raise SourceError unless cfg.input.fps_override is set. BGR->gray uint8 2-D. Frame(index, timestamp_s=index/fps, source_id=path, pointing=None, meta={"decoded_frames": n}). read() returns None at end of stream and keeps returning None. reset() seeks to frame 0. close(). Context manager support. Do NOT resize frames. Warn (logging) if CAP_PROP_POS_MSEC deviates >20% from index/fps (VFR).
- src/skylock/core/errors.py: add SourceError.
- app/factory.py: for InputKind.MP4 build Mp4Source, an effective CameraConfig derived from video width/height and cfg.input.mp4_assumed_fov_h_deg (square pixels, vertical FOV derived) WITHOUT mutating the original config; no gimbal; Session computes and returns commands but does not apply them; truth is None.
- scripts/gen_test_video.py: render a deterministic MP4 (fourcc mp4v) from SimulationSource with a fixed-pointing gimbal and a moving target + noise; CLI args: --out, --seconds, --seed.
- Do NOT put any ground-truth loading in src/skylock/input/.

6. TESTS
tests/unit/input/test_video.py: frame count, strictly increasing timestamps at 1/fps, end-of-stream returns None repeatedly, reset replays identical arrays, missing file and corrupt file raise SourceError, colour-patch grayscale conversion value, fps<=0 handling.
tests/integration/test_mp4_pipeline.py: generate a video into tmp_path via the script's function; run Session on it; assert the tracker reaches TRACK; assert the PipelineOutput sequence equals running TrackingPipeline directly on the same decoded frames (proves single shared pipeline). Skip with a clear reason if cv2.VideoWriter cannot open mp4v; print which.
Run `ruff check src tests`, `mypy src/skylock/core src/skylock/config`, `pytest -q`.

7. ACCEPTANCE CRITERIA
All tests pass (or skip only for documented codec absence); same pipeline class and config path used for both inputs; end-of-stream is explicit.

8. DO NOT
- Do not fork or duplicate pipeline/detector/tracker code for video. Do not resize frames. Do not default fps silently. Do not commit binary videos. Do not add metrics.

9. FINAL REPORT
Tests + results (including any skips and why), files created/modified, known limitations (codec, VFR), remaining work.
```

---

### Phase 8: Metrics + Logging

#### Objective
Honest metrics with explicit status, consumed from `(PipelineOutput, Frame meta, GroundTruthSample|None)`, plus per-frame logging.

#### Scope
`metrics/*`, `app/session.py` (hook), tests, `docs/METRICS.md`.

#### Dependencies
Phases 5–7.

#### Implementation Tasks
1. `status.py`: `Metric[T]` frozen dataclass `{value: T|None, status: MetricStatus, reason: str|None}`; constructors `measured(v)`, `not_run(reason)`, `not_acquired(reason)`, `failed(reason)`. Invariant: `value is None ⇔ status != MEASURED` (enforced in `__post_init__`). JSON serialisation emits `null`.
2. Definitions (documented in `docs/METRICS.md`):
   - **acquisition_time_s**: first TRACK entry time − reference. Two variants: `from_start` and `from_first_observable` (first frame where GT target visible in FOV; needs GT ⇒ `NOT_RUN` for MP4 without sidecar). Never acquired → `NOT_ACQUIRED`.
   - **tracking_error_px**: |estimate px − GT px| over frames where state==TRACK and target visible; stats mean/rms/p95/max + n; no such frames → `NOT_ACQUIRED`/`NOT_RUN`.
   - **pointing_error_px**: |GT px − boresight| same frame set.
   - **centering_error_px**: |estimate px − boresight| (estimate-only; the only error measurable for MP4 w/o GT).
   - **reacquisition_time_s**: per event, time from GT target reappearance to TRACK (GT available) else from LOST entry to TRACK (flagged `basis="tracker_only"`); success requires ≤ `reacquire_timeout`; aggregated list + max + mean; no loss events → `NOT_RUN` ("no loss event occurred"), event never recovered → `FAILED`.
   - **target_loss_rate**: post-acquisition frames not in TRACK ÷ post-acquisition frames.
   - **lock_retention**: post-acquisition frames with state==TRACK and (GT available ? pointing_error ≤ lock_radius : centering_error ≤ lock_radius) ÷ post-acquisition frames.
   - **detection_rate**: frames with ≥1 detection near GT (≤ gate) ÷ frames with GT visible (GT required; else `NOT_RUN`); plus `detection_present_rate` (estimate-only).
   - **fps_processing**: frames ÷ Σ latency (pipeline only) and end-to-end wall FPS; **latency_ms** mean/p50/p95/max; **missed_frames**: frames whose latency > frame period (+ source-dropped count kept separate); zero frames processed → `NOT_RUN`.
   - successful_acquisition / successful_reacquisition booleans as `Metric[bool]`.
3. `collector.py`: `MetricsCollector(cfg)`: `record(step: StepResult)`; incremental (O(1) memory per frame except arrays kept as compact `float32` lists), `finalize() -> RunMetrics`, `reset()`.
4. `requirements.py`: `evaluate(run_metrics, cfg.requirements) -> dict[str, Verdict]`: any non-MEASURED metric ⇒ `INDETERMINATE` (never PASS); overall verdict = FAIL if any FAIL, INDETERMINATE if any INDETERMINATE and no FAIL, PASS only if all PASS.
5. `logger.py`: `FrameLogger` writing JSONL (one line/frame: index, t, state, estimate, detections count, latency; GT fields only when present, prefixed `gt_`), `RunRecord` writer; `null` for missing values.
6. `GroundTruthSidecar` (CSV) loader in `metrics/sidecar.py` for optional MP4 evaluation.
7. Hook in `Session`: optional `collector`, invoked after each step with `StepResult` (the collector, not the pipeline, sees truth).

#### Acceptance Criteria
- Unit tests on **hand-computed** synthetic timelines for each metric (exact expected numbers).
- No code path yields 0 for an unmeasured metric; a grep-style test asserts absence of `or 0`, `or 60`, `?? 0` patterns in `metrics/`.
- MP4 run without sidecar: pointing/tracking/detection/acquisition-from-observable are `NOT_RUN` with reasons; centering error & FPS are `MEASURED`.
- Never-acquired run: acquisition `NOT_ACQUIRED`, requirements verdicts `INDETERMINATE`/`FAIL` (acquisition = FAIL when the run had a full observable window and never locked — rule documented), overall never PASS.
- JSON output contains `null`, never `NaN`/0 placeholders.

#### Tests
`tests/unit/metrics/test_status.py, test_calculators.py, test_collector.py, test_requirements.py, test_logger.py, test_no_fake_defaults.py, test_sidecar.py`; `tests/integration/test_sim_metrics.py`, `tests/integration/test_mp4_metrics.py`.

#### Files Created / Modified / Deleted
Created: `metrics/*`, `docs/METRICS.md`, tests. Modified: `app/session.py`. Deleted: none.

#### Risks
Metric definition disputes (documented, versioned via `metrics_version`); float32 arrays memory on long runs.

#### Antigravity Prompt
```text
You are implementing Phase 8 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 2.2 and "Phase 8" (metric definitions are normative); docs/PS_SPEC.md section 7; src/skylock/core/{types,enums}.py; src/skylock/app/session.py.

2. CURRENT STATE
Closed-loop simulation and MP4 both run through Session producing StepResult(frame, output, command, truth|None). No metrics or logging.

3. GOAL
Implement the metrics package with explicit measurement status, requirement evaluation with tri-state verdicts, and a per-frame logger. Ground truth is consumed here and nowhere else.

4. FILES TO INSPECT
legacy/js/src/tracking/metrics.js (reference for WHAT to measure; it contains fake fallbacks like `fps || 60` and 0-for-empty which you must NOT reproduce), legacy/docs/METRICS.md.

5. IMPLEMENTATION
Create src/skylock/metrics/{status.py,collector.py,calculators.py,requirements.py,logger.py,sidecar.py} and docs/METRICS.md.
- Metric[T] frozen dataclass {value, status, reason}; invariant value is None iff status != MEASURED; constructors measured/not_run/not_acquired/failed; JSON emits null.
- Implement EXACTLY the metric definitions in the plan's Phase 8 section: acquisition_time (from_start and from_first_observable), tracking_error_px, pointing_error_px, centering_error_px (mean/rms/p95/max/n each), reacquisition events (GT reappearance basis, else tracker_only basis flagged), target_loss_rate, lock_retention, detection_rate and detection_present_rate, processing fps (pipeline-only and end-to-end), latency stats, missed_frames (latency > frame period; source-dropped separate), successful_acquisition and successful_reacquisition as Metric[bool]. Include `metrics_version = "1"` in RunMetrics.
- MetricsCollector(cfg): record(step_result), finalize()->RunMetrics, reset(). Memory-lean (float32 arrays).
- requirements.evaluate(run_metrics, cfg.requirements)->dict[str, Verdict]; non-MEASURED => INDETERMINATE (never PASS); overall: FAIL if any FAIL else INDETERMINATE if any INDETERMINATE else PASS. Rule: acquisition is FAIL (not INDETERMINATE) when the run had a full observable window >= acquisition_max_s and never reached TRACK.
- FrameLogger: JSONL per frame, GT fields only when present with `gt_` prefix, null for missing. RunRecord writer.
- sidecar.py: GroundTruthSidecar CSV loader (frame,x,y,visible) producing GroundTruthSample-like inputs for MP4 evaluation; lives in metrics/, never in input/.
- Session: optional collector hook that receives the whole StepResult after each step.

6. TESTS
tests/unit/metrics/: hand-computed synthetic timelines with exact expected values for every metric; test_status invariant; test_requirements tri-state logic incl. never-acquired; test_no_fake_defaults (regex-scan src/skylock/metrics for `or 0`, `or 60`, `?? 0`, `default=0` patterns on metric values and fail on match); logger null handling; sidecar parsing.
Integration: sim run with a scripted occlusion window -> reacquisition metric measured; MP4 run without sidecar -> ground-truth metrics NOT_RUN with reasons while centering error and FPS are MEASURED; zero-frame run -> everything NOT_RUN.
Run `ruff check src tests`, `mypy src/skylock/core src/skylock/config`, `pytest -q`.

7. ACCEPTANCE CRITERIA
All tests pass; no unmeasured metric can become 0/60/1.0; JSON has null not NaN; overall verdict cannot be PASS with any non-MEASURED required metric; architecture tests pass (tracking/vision/control still do not import metrics).

8. DO NOT
- Do not compute metrics inside pipeline/tracker/controller. Do not default FPS or latency. Do not change requirement thresholds. Do not give the metrics collector access to mutate pipeline state.

9. FINAL REPORT
Tests + results, files created/modified, any metric-definition ambiguities you resolved (list them), known limitations, remaining work.
```

---

### Phase 9: Deterministic Benchmark Framework

#### Objective
Reproducible, GUI-independent benchmark runs with full provenance and isolation.

#### Scope
`benchmark/*`, `app/cli.py` (`skylock bench`), `scripts/run_benchmark.py`, tests, `docs/BENCHMARK.md`.

#### Dependencies
Phases 6–8.

#### Implementation Tasks
1. `scenario.py`: `Scenario(id, description, overrides: Mapping[str, Any], duration_s, seeds: tuple[int,...], input: InputKind, mp4_path|None, tags)`; `apply(base_cfg, seed) -> SkyLockConfig` via `config.io.override`.
2. `catalog.py` (function `builtin_scenarios()`, no module-level mutable): at minimum `S01_line_clean`, `S02_circle_clean`, `S03_fig8_clean`, `S04_random_clean`, `S05_line_spec_noise` (σ=20, S&P, Poisson), `S06_jitter20`, `S07_platform20`, `S08_haze`, `S09_fog`, `S10_rain`, `S11_low_light`, `S12_occlusion_reacq` (visibility window 0.5 s), `S13_all_disturbances`, `S14_multi_target`, `S15_slew10`, `S16_mp4` (user-provided path; `NOT_RUN` if absent). Initial target offsets declared per scenario so acquisition ≤ 2 s is physically feasible (≤ FOV/2 + reach at slew) and stated in the scenario description.
3. `runner.py`: `BenchmarkRunner.run(scenario, seed) -> RunRecord`: builds a **fresh** `Session` per run (no shared objects), optionally in a subprocess (`multiprocessing` spawn) with `isolate=True` to prove no global state; wall-clock stopped only around the loop. `RunRecord`: `{run_id, scenario_id, seed, software_version, python/numpy/opencv versions, platform, config_snapshot, config_hash, input_source, duration_s, frames, metrics, verdicts, overall_verdict, started_at_utc, wall_time_s, git_commit|None}`.
4. `report.py`: JSON (schema version) + Markdown table; `null` retained; aggregate across seeds reports counts of PASS/FAIL/INDETERMINATE and statistics **only over MEASURED values** with n shown.
5. `compare.py`: `compare_runs(a, b, tol)` comparing deterministic fields (state timeline hash, estimates, error stats, acquisition time) exactly or within `tol=1e-9`; excludes wall-clock fields (`latency`, `fps`, timestamps); returns a diff list.
6. CLI: `skylock bench --scenarios S01,S05 --seeds 1,2,3 --out runs/…` and `--all`; exit code 0 always when the harness ran (verdicts in report), non-zero only on harness error; `--fail-on-verdict` optional.
7. Deterministic seeds: `seed` flows only through `SkyLockConfig.seed` → `derive_rng`. No `time`-based seeds. `Scenario` seeds explicit.

#### Acceptance Criteria
- Same scenario+seed+config run twice in-process **and** in separate processes ⇒ `compare_runs` returns no diffs.
- Running S05 then S01 gives the same S01 result as S01 alone (isolation).
- Every `RunRecord` contains all required provenance fields; missing MP4 ⇒ `NOT_RUN` record, not a crash and not zeros.
- Benchmark imports no `PySide6` (tested by running in an environment where PySide6 import is blocked via `sys.modules` stub).
- Report shows PASS/FAIL/INDETERMINATE honestly — including failures.

#### Tests
`tests/benchmark/test_determinism.py, test_isolation.py, test_provenance.py, test_report.py, test_no_gui_dependency.py, test_catalog_valid.py` (every scenario config validates).

#### Files Created / Modified / Deleted
Created: modules + docs + tests. Modified: `app/cli.py`, `app/main.py`. Deleted: none.

#### Risks
Cross-platform float nondeterminism (OpenCV threading): pin `cv2.setNumThreads(1)` inside runner for benchmark runs and document; Poisson generator version drift (record numpy version).

#### Antigravity Prompt
```text
You are implementing Phase 9 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 2.3, 3 and "Phase 9"; src/skylock/app/{session,factory}.py; src/skylock/metrics/*; src/skylock/config/io.py.

2. CURRENT STATE
Session + metrics collector + requirements evaluation exist. No benchmark package, no CLI beyond version print.

3. GOAL
Deterministic, isolated, provenance-complete benchmark framework, independent of any GUI.

4. FILES TO INSPECT
legacy/js/src/tracking/{benchmark,scenarios,exporter}.js and legacy/docs/BENCHMARK_SCHEMA.md (reference only: they used global singletons and produced zero-filled results).

5. IMPLEMENTATION
Create src/skylock/benchmark/{scenario,catalog,runner,report,compare}.py, update src/skylock/app/{cli,main}.py, scripts/run_benchmark.py, docs/BENCHMARK.md.
- Scenario dataclass and apply(base_cfg, seed) using config.io.override.
- catalog.builtin_scenarios() -> tuple[Scenario,...] (a function; no module-level mutable): S01_line_clean, S02_circle_clean, S03_fig8_clean, S04_random_clean, S05_line_spec_noise (gaussian 20 + S&P + Poisson), S06_jitter20, S07_platform20, S08_haze, S09_fog, S10_rain, S11_low_light, S12_occlusion_reacq (0.5 s visibility gap), S13_all_disturbances, S14_multi_target, S15_slew10, S16_mp4 (path supplied at runtime; NOT_RUN record if absent). Each scenario documents its initial target offset so that 2 s acquisition is physically feasible at 5 deg/s (IFOV 0.00625 deg/px; 2 s reach = 10 deg).
- BenchmarkRunner.run(scenario, seed, isolate=False)->RunRecord: fresh Session per run; isolate=True runs in a spawned subprocess; call cv2.setNumThreads(1); RunRecord includes run_id, scenario_id, seed, software_version (skylock.__version__), python/numpy/opencv versions, platform, config_snapshot, config_hash, input_source, duration_s, frames, metrics, verdicts, overall_verdict, started_at_utc, wall_time_s, git_commit (None if unavailable).
- report.py: JSON with schema_version + Markdown; nulls preserved; aggregates over seeds count verdicts and compute statistics ONLY over MEASURED values, showing n.
- compare.compare_runs(a,b,tol=1e-9): compares deterministic fields (state timeline hash, estimates hash, error stats, acquisition time) and ignores wall-clock fields.
- CLI: `skylock bench --scenarios S01,S05 --seeds 1,2,3 --out runs/x [--isolate] [--all] [--fail-on-verdict]`; exit non-zero only for harness errors unless --fail-on-verdict.
- Seeds flow only via SkyLockConfig.seed -> derive_rng. No time-based seeds.

6. TESTS
tests/benchmark/: test_determinism (in-process x2 and cross-process: compare_runs empty), test_isolation (S05 then S01 == S01 alone), test_provenance (all fields present), test_report (nulls, aggregation n), test_no_gui_dependency (stub PySide6 to raise ImportError; run a short benchmark), test_catalog_valid (every scenario's config validates for its seeds). Use short durations in tests (<= 6 s sim) and mark long ones `slow`.
Run `ruff check src tests`, `pytest -q`, then `python scripts/run_benchmark.py --scenarios S01_line_clean --seeds 1 --out runs/smoke` and include the JSON path.

7. ACCEPTANCE CRITERIA
Determinism, isolation, provenance and no-GUI tests pass; report contains honest FAIL/INDETERMINATE where applicable; missing MP4 yields NOT_RUN.

8. DO NOT
- Do not tune tracker/detector parameters to make scenarios pass. Do not share objects between runs. Do not import PySide6. Do not use wall-clock or `random` for seeds. Do not convert failures to passes; do not omit failed runs from reports.

9. FINAL REPORT
Tests + results, the actual smoke benchmark verdicts/numbers (unedited), files created/modified, known limitations, remaining work.
```

---

### Phase 10: PySide6 GUI (Thin Presentation Layer)

#### Objective
Clean Qt front-end over `Session`/`BenchmarkRunner`; zero algorithm code in widgets.

#### Scope
`ui/*`, `app/main.py` (`skylock gui`), tests (`gui` marker, offscreen).

#### Dependencies
Phases 6–9.

#### Implementation Tasks
1. `ui/worker.py`: `SessionWorker(QObject)` running `Session.step()` loop in a `QThread` at configured FPS (or free-run); emits `frame_ready(FrameView)` where `FrameView` is an immutable UI DTO (image, overlays, telemetry) built from `StepResult`. Commands from GUI (start/stop/reset/manual rate/config change) arrive as queued slots; config edits create a **new** `SkyLockConfig` and rebuild the session (no mutation).
2. `ui/main_window.py`: left dock controls, centre camera view, right telemetry, bottom benchmark tab.
   - Controls: input source (Simulation/MP4 + file picker), start/stop/reset, AUTO/MANUAL (arrow keys or buttons → manual rates), target (motion kind + params, size 5–20, shape, count, random initial position), camera (resolution, FOV, FPS, slew ≤10), disturbances (independent toggles + sliders, atmosphere combo), seed (with "randomise" button showing the seed used), scenario combo + Run/Run-all benchmark.
   - Display: `QImage` mono view with overlays (detected centroid ring, estimated position cross, gate box, boresight crosshair; ground-truth marker **only** when "Show ground truth (debug)" is ticked and source is simulation), state badge (colour per state), pan/tilt, FPS, latency, acquisition time, tracking error, lock status; `—` for `None` metrics (never `0`).
   - Benchmark tab: table of `RunRecord` rows with verdict colours (PASS/FAIL/INDETERMINATE/NOT_RUN), export JSON/MD buttons; benchmark runs in a separate process/thread and never touch the live session.
3. Widgets bind to config via a small `ConfigEditor` that builds a new config through `config.io.override` and shows `ConfigError` messages inline.
4. Keep UI files small (< 300 lines each); no tracking maths; no imports of `tracking`, `vision`, `control`, `simulation` internals (only `app`, `config`, `core` types, `benchmark` API). Architecture test enforces.
5. Offscreen tests via `QT_QPA_PLATFORM=offscreen`.

#### Acceptance Criteria
- `skylock gui` launches; Start runs simulation showing frames at ≥ 20 UI updates/s at defaults (frame-skip allowed for UI only; pipeline still processes every frame).
- Changing any control produces a valid new config or an inline error, never a crash.
- Benchmark tab runs a scenario and displays a verdict without freezing the UI.
- No metric shows `0` for `None` values (test).
- Architecture test: `ui` imports only allowed packages; no other package imports `ui`.

#### Tests
`tests/gui/test_main_window.py` (offscreen, `gui` marker): construct window, start worker for 30 frames, assert telemetry labels update, assert `—` for NOT_RUN metrics, assert invalid slew (11) shows error and does not start, assert benchmark tab populates from a stubbed runner.

#### Files Created / Modified / Deleted
Created: `ui/*`, tests. Modified: `app/main.py`. Deleted: none.

#### Risks
Thread-safety (image buffers copied into DTO); Qt in CI (offscreen); opencv/PySide6 plugin conflict (headless wheel — set in Phase 0).

#### Antigravity Prompt
```text
You are implementing Phase 10 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 1 (import table), 2 and "Phase 10"; src/skylock/app/{session,factory,main,cli}.py; src/skylock/benchmark/*; src/skylock/config/*.

2. CURRENT STATE
Core, simulation, MP4, metrics and benchmark all work headless via Session and BenchmarkRunner. No GUI.

3. GOAL
A clean PySide6 GUI that is only a presentation/control layer.

4. FILES TO INSPECT
src/skylock/app/session.py, src/skylock/metrics/status.py, src/skylock/benchmark/runner.py. Do NOT read legacy/js UI files for structure; the old 700-line HTML UI must not be reproduced.

5. IMPLEMENTATION
Create src/skylock/ui/{__init__.py,main_window.py,worker.py,config_editor.py,panels/{controls,telemetry,benchmark}.py,widgets/{camera_view,state_badge}.py}. Each file < 300 lines.
- SessionWorker(QObject) in a QThread: loops Session.step(); emits frame_ready(FrameView) (frozen dataclass DTO: image copy, overlay coordinates, telemetry, metrics snapshot). Start/stop/reset/manual-rate/apply-config are queued slots. Applying config = build a NEW SkyLockConfig via config.io.override and rebuild the Session; never mutate.
- MainWindow: input source (Simulation / MP4 with file picker), Start/Stop/Reset, AUTO/MANUAL (arrow keys), target controls (motion kind+params, size 5-20, shape, count, random initial), camera controls (resolution, FOV, FPS>=30, slew<=10), disturbance controls (independent enable + slider per component; atmosphere combo), seed spinbox + randomise button (shows seed used), scenario combo + Run / Run-all benchmark.
- CameraView draws mono frame plus overlays: detected centroid ring, estimated cross, gate box, boresight crosshair; ground-truth marker ONLY if the 'Show ground truth (debug)' checkbox is on and the source is simulation.
- Telemetry panel: state badge (colour per TrackState), pan/tilt, FPS, latency, acquisition time, tracking error, lock status. Any None metric renders as an em dash, never 0.
- Benchmark panel: runs BenchmarkRunner in a separate thread/process (never touching the live session), table with verdict colours (PASS/FAIL/INDETERMINATE/NOT_RUN), export JSON/Markdown.
- ConfigEditor turns widget values into a new config and shows ConfigError messages inline.
- app/main.py: `skylock gui` lazily imports skylock.ui (PySide6 is an optional extra); print a clear message if PySide6 is missing.
- ui/ may import only skylock.app, skylock.config, skylock.core (types), skylock.benchmark (public API). Update the architecture test.

6. TESTS
tests/gui/test_main_window.py with marker gui and QT_QPA_PLATFORM=offscreen: window constructs; worker runs 30 frames and labels update; None metrics show the em dash; invalid slew (11) shows an inline error and does not start; benchmark tab populates using a stub runner; ground-truth marker hidden by default. Run: `QT_QPA_PLATFORM=offscreen pytest -q -m gui`, `pytest -q`, `ruff check src tests`.

7. ACCEPTANCE CRITERIA
GUI launches and runs the simulation; controls produce valid configs or inline errors; benchmark does not freeze UI; no 0-for-None; architecture test passes.

8. DO NOT
- No tracking/vision/control logic in widgets. Do not import skylock.tracking/vision/control/simulation from ui. Do not let benchmark code depend on ui. Do not mutate config objects. Do not add web views/HTML. Do not add dependencies other than PySide6.

9. FINAL REPORT
Tests + results, screenshot description (or saved offscreen grab path), files created/modified, known limitations, remaining work.
```

---

### Phase 11: Integration Tests + Performance Validation

#### Objective
Prove the end-to-end behaviour and measure performance honestly against the spec.

#### Scope
`tests/e2e/*`, `tests/perf/*`, `scripts/perf_report.py`, `docs/VALIDATION_REPORT.md`; bug fixes discovered (limited, listed).

#### Dependencies
Phases 1–10.

#### Implementation Tasks
1. E2E scenario tests using `Session` + `MetricsCollector`: start → target enters FOV → ACQUIRE → TRACK → target moves (each motion kind) → camera follows (boresight error bounded) → target disappears (visibility window) → LOST → REACQUIRE → TRACK → metrics generated and serialisable.
2. Negative tests: target never in reach ⇒ `NOT_ACQUIRED`, verdict not PASS; target disappears permanently ⇒ REACQUIRE→SEARCH by deadline.
3. Ground-truth firewall tests: poisoned-truth determinism test (truth corrupted ⇒ identical pipeline outputs); AST test extended over all packages.
4. Performance: `scripts/perf_report.py` measures at 640×480 with all disturbances on: per-stage times (render, disturbances, detect, track, control), pipeline FPS and end-to-end FPS over ≥ 1,000 frames, 3 repeats, reports median/p95 and machine info. `tests/perf/` soft thresholds: pipeline ≥ 20 FPS on the CI reference (marker `perf`, skipped by default).
5. Requirement sweep: run built-in scenarios × 5 seeds; produce `docs/VALIDATION_REPORT.md` with the **unedited** table of verdicts. Where requirements are not met, document root causes and open issues — do not adjust thresholds or hide failures. Fixes to genuine algorithm bugs are allowed but each must have a regression test and be listed.
6. Determinism sweep: every scenario run twice ⇒ `compare_runs` clean.
7. MP4 e2e: generated video, end-of-stream, metrics with `NOT_RUN` ground-truth metrics, and with sidecar ground truth → measured.

#### Acceptance Criteria
- Full e2e chain test passes with real state transitions asserted in order.
- Determinism sweep clean; isolation clean.
- Performance report produced with real numbers; if < 20 FPS pipeline FPS it is reported as FAIL with profiling summary.
- `docs/VALIDATION_REPORT.md` matches the JSON outputs byte-for-byte in its numbers (generated by script, not hand-typed).

#### Tests
`tests/e2e/test_full_chain.py, test_negative_cases.py, test_mp4_e2e.py, test_truth_firewall.py, test_determinism_sweep.py`; `tests/perf/test_pipeline_fps.py`.

#### Files Created / Modified / Deleted
Created: tests, `scripts/perf_report.py`, `scripts/gen_validation_report.py`, `docs/VALIDATION_REPORT.md`. Modified: only files with listed bug fixes. Deleted: none.

#### Risks
Discovering that requirements are unmet under harsh combined disturbances (an honest outcome); flaky perf tests on shared CI.

#### Antigravity Prompt
```text
You are implementing Phase 11 of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 2.2, 5 (Phase 11), 6 (testing strategy) and 7; docs/PS_SPEC.md section 7; src/skylock/app/*, src/skylock/benchmark/*, src/skylock/metrics/*.

2. CURRENT STATE
All components and the GUI exist. Unit/integration tests exist per phase. No end-to-end proof or performance report yet.

3. GOAL
Write the end-to-end, negative, firewall, determinism and performance validation, and produce an honest validation report from real runs.

4. FILES TO INSPECT
tests/**, src/skylock/app/session.py, src/skylock/benchmark/catalog.py, src/skylock/metrics/requirements.py.

5. IMPLEMENTATION
- tests/e2e/test_full_chain.py: for each motion kind (line, circle, figure8, random) run Session+MetricsCollector on a scenario where the target starts inside the FOV; assert ordered state transitions SEARCH->ACQUIRE->TRACK (from the event log), boresight error (GT, computed in the test) bounded after lock, then a scenario with a 0.5 s visibility window asserting TRACK->LOST->(REACQUIRE)->TRACK, metrics serialisable to JSON with nulls where unmeasured.
- tests/e2e/test_negative_cases.py: target beyond reach => acquisition NOT_ACQUIRED and overall verdict not PASS; permanent disappearance => REACQUIRE->SEARCH at reacquire_timeout_s +/- one frame.
- tests/e2e/test_truth_firewall.py: (a) run twice with the simulation ground-truth values deliberately corrupted after rendering; PipelineOutput sequences must be identical; (b) extended AST scan over all non-metrics packages for GroundTruthSample usage.
- tests/e2e/test_determinism_sweep.py: every built-in scenario, 1 seed, run twice with compare_runs => no diffs (short durations; mark long ones slow).
- tests/e2e/test_mp4_e2e.py: generated MP4 -> end-of-stream reached; GT metrics NOT_RUN without sidecar; with a sidecar produced by the generator, GT metrics MEASURED.
- scripts/perf_report.py: at 640x480 with all disturbances enabled, >=1000 frames, 3 repeats: per-stage timing (render, disturbances, detect, track, control), pipeline FPS and end-to-end FPS, median/p95, machine info; write JSON to runs/perf/.
- scripts/gen_validation_report.py: run builtin scenarios x seeds 1..5, write runs/validation/*.json and generate docs/VALIDATION_REPORT.md FROM THE JSON (no hand-typed numbers). Include PASS/FAIL/INDETERMINATE counts, per-requirement tables, failures with root-cause notes.
- tests/perf/test_pipeline_fps.py (marker perf): soft-assert pipeline FPS >= 20; skipped by default.
- If you find genuine bugs, fix minimally, add a regression test, and list each fix in the report.

6. TESTS
Run: `pytest -q`, `pytest -q -m slow`, `pytest -q -m perf`, `QT_QPA_PLATFORM=offscreen pytest -q -m gui`, `ruff check src tests`, `mypy src/skylock/core src/skylock/config`, `python scripts/perf_report.py`, `python scripts/gen_validation_report.py`.

7. ACCEPTANCE CRITERIA
Ordered state-transition assertions pass; negative cases behave; firewall tests pass; determinism sweep clean; real perf JSON and a generated validation report exist and contain unedited results.

8. DO NOT
- Do NOT change thresholds, requirements, or detector/tracker/controller parameters to make results pass. Do NOT hand-edit the validation report numbers. Do NOT suppress or skip failing scenarios. No large refactors.

9. FINAL REPORT
Tests + results, headline verdict table (unedited), perf numbers, bug fixes with regression tests, files created/modified, known limitations, remaining work.
```

---

### Phase 12: PyInstaller Packaging + Documentation + Final Cleanup

#### Objective
Standalone executable, final docs, removal of legacy material.

#### Scope
`packaging/skylock.spec`, `scripts/build_exe.py`, `docs/*`, `README.md`, deletion of `legacy/`.

#### Dependencies
Phases 0–11.

#### Implementation Tasks
1. `packaging/skylock.spec`: entry `src/skylock/app/main.py` (or a tiny `scripts/entry.py` calling `main()`), `--windowed` for GUI build plus console variant `skylock-cli` for `bench`/`run`; hidden imports for PySide6 plugins as needed; exclude test/dev packages; one-folder build first (`onedir`), one-file optional; include `docs/USER_GUIDE.md`; **opencv-python-headless only**; version stamped from `skylock.__version__`.
2. `scripts/build_exe.py`: runs PyInstaller, then a smoke test: `skylock-cli --version`, `skylock-cli bench --scenarios S01_line_clean --seeds 1 --out <tmp>` from the built artifact, and a GUI launch with `--self-test` flag (constructs window offscreen, runs 10 frames, exits 0).
3. Add `skylock gui --self-test` to `app/main.py`.
4. Docs: `README.md` (what it is, install, run GUI, run benchmark, run MP4, build exe, architecture diagram from §1–2), `docs/ARCHITECTURE.md` (final, matches code), `docs/USER_GUIDE.md`, `docs/CONFIG.md`, `docs/METRICS.md`, `docs/BENCHMARK.md`, `docs/DISTURBANCES.md`, `docs/CONTROL_DESIGN.md`, `docs/VALIDATION_REPORT.md` retained.
5. Final cleanup: delete `legacy/`; ensure no references to it (grep); remove unused deps; `ruff format`; `mypy` extended to all packages if feasible; regenerate lock; `git tag v1.0.0` guidance.
6. Confirm architecture and full test suite still green after deleting legacy.

#### Acceptance Criteria
- Built executable launches on a machine without Python (verify at minimum in a clean venv-free directory; document the manual clean-machine check).
- Smoke benchmark from the built exe outputs a valid `RunRecord` JSON.
- `grep -R "legacy" src tests scripts docs README.md` finds nothing meaningful.
- All tests + ruff pass; docs match commands that actually work (each command in README executed in the report).

#### Tests
`tests/packaging/test_spec_valid.py` (spec parses, entry exists), `tests/unit/app/test_cli.py`; build smoke script (manual/CI job, not default pytest).

#### Files Created / Modified / Deleted
Created: spec, build script, docs. Modified: `README.md`, `pyproject.toml`, `app/main.py`. Deleted: `legacy/` entirely.

#### Risks
PyInstaller + Qt plugin discovery, OpenCV binary size, Windows Defender false positives, antivirus on onefile.

#### Antigravity Prompt
```text
You are implementing Phase 12 (final) of the SkyLock Python rebuild.

1. READ FIRST
docs/MASTER_PLAN.md sections 1, 5 (Phase 12), 7, 8, 9; docs/VALIDATION_REPORT.md; pyproject.toml; src/skylock/app/main.py.

2. CURRENT STATE
All phases 0-11 complete; tests pass; validation report exists; legacy/ still in the repo.

3. GOAL
Produce a working PyInstaller build, final documentation, and remove legacy material.

4. FILES TO INSPECT
pyproject.toml, src/skylock/app/{main,cli}.py, src/skylock/ui/*, README.md, docs/*.

5. IMPLEMENTATION
a) Add `--self-test` to `skylock gui` (offscreen-capable: construct MainWindow, run 10 frames, exit 0) and `--version` to CLI.
b) packaging/skylock.spec: onedir build, windowed GUI executable `skylock` and console executable `skylock-cli`; hidden imports for PySide6 as needed; excludes: pytest, mypy, ruff, tests; datas: docs/USER_GUIDE.md; ensure opencv-python-headless is what is bundled.
c) scripts/build_exe.py: run PyInstaller from the spec; then smoke-test the built artifacts: `skylock-cli --version`, `skylock-cli bench --scenarios S01_line_clean --seeds 1 --out <tmp>` (assert valid JSON RunRecord), `skylock --self-test`.
d) Write README.md, docs/ARCHITECTURE.md (matching the real code tree), docs/USER_GUIDE.md. Update docs/CONFIG.md, METRICS.md, BENCHMARK.md, DISTURBANCES.md, CONTROL_DESIGN.md if they drifted. EXECUTE every command shown in README and record outputs in your report.
e) Delete legacy/ entirely; grep for references to it and remove them; remove unused dependencies; run `ruff check --fix` and `ruff format`; extend mypy to all packages if it passes, otherwise document exclusions; regenerate lock file.
f) Add tests/packaging/test_spec_valid.py and tests/unit/app/test_cli.py.

6. TESTS
`pytest -q`, `QT_QPA_PLATFORM=offscreen pytest -q -m gui`, `ruff check src tests`, `python scripts/build_exe.py`, then run the built executables' smoke tests.

7. ACCEPTANCE CRITERIA
Built exe launches and self-tests; built CLI bench produces a valid RunRecord; no meaningful references to legacy remain; all tests and lint pass; README commands verified.

8. DO NOT
- Do not change algorithm behaviour or thresholds. Do not commit build artifacts (dist/, build/). Do not use opencv-python (non-headless). Do not remove docs/PS_SPEC.md or docs/VALIDATION_REPORT.md.

9. FINAL REPORT
Tests + results, build output paths and sizes, smoke-test results, files created/modified/deleted, known limitations (e.g. clean-machine test still manual), remaining work.
```

---

## 6. Testing Strategy (summary matrix)

| Level | What | Where | Phase |
|---|---|---|---|
| Unit | config validation; geometry; RNG streams; motion models; sprite/camera; each disturbance; detector; centroid; association; Kalman (convergence + NIS); state machine (all transitions); search patterns; PID; controller; gimbal (limits, no-snap); metrics calculators; requirement evaluator; logger | `tests/unit/**` | 1–8 |
| Integration | synthetic frame → detector → tracker; simulation → frame → detector → tracker (open loop); tracking → controller → gimbal (closed loop); target loss → reacquisition; session reset determinism; MP4 == direct frames | `tests/integration/**` | 4–8 |
| End-to-end | sim start → enters FOV → ACQUIRE → TRACK → moves → camera follows → disappears → LOST → REACQUIRE → TRACK → metrics; negative cases | `tests/e2e/**` | 11 |
| MP4 | load, decode, same pipeline, end-of-stream, metrics NOT_RUN vs MEASURED | `tests/unit/input`, `tests/e2e/test_mp4_e2e.py` | 7, 11 |
| Benchmark | seed determinism (in-process + cross-process), isolation, provenance, no-GUI | `tests/benchmark/**` | 9 |
| Architecture | import boundaries, no global state, ground-truth firewall (AST + poisoned truth) | `tests/architecture/**`, `tests/e2e/test_truth_firewall.py` | 0–11 |
| GUI | offscreen smoke, None→"—", validation errors | `tests/gui/**` | 10 |
| Perf | detector latency, pipeline FPS ≥ 20 | `tests/perf/**` + `scripts/perf_report.py` | 4, 11 |

Determinism tolerance: deterministic fields equal within `1e-9` (bit-exact expected on the same machine); wall-clock fields are excluded from comparison.

## 7. Performance Plan

- Camera 640×480 mono @ ≥ 30 FPS; pipeline (detector + tracker) target ≥ 20 FPS ⇒ ≤ 50 ms/frame, design budget ≤ 15 ms.
- Levers (all pre-planned, none are threshold tuning): ROI detection in TRACK/LOST, box-filter background, bbox-local centroiding, single-thread OpenCV in benchmarks, float32 rendering, Poisson normal approximation for large λ (documented).
- Simulation render/disturbance cost is reported separately and is **not** counted in processing FPS, but end-to-end FPS is reported too.
- Benchmark measures real behaviour; failures are reported, never masked.

## 8. Final Acceptance Checklist

- [ ] `python -m skylock`, `skylock gui`, `skylock bench`, `skylock run --mp4 file.mp4` all work
- [ ] One config model; no module-level config instances; validation rules of §3 all tested
- [ ] FOV 4°×3°, 640×480, ≥30 FPS, slew 5°/s default, ≤10°/s hard cap
- [ ] Monochrome uint8 frames; sim and MP4 share `Frame` and the same `TrackingPipeline`
- [ ] Four motion models, configurable size/shape/count/seed/initial position
- [ ] All disturbances independent, seeded, resettable; ±20 px/frame and σ ≤ 20 enforced
- [ ] Classical detector; sub-pixel centroid; documented detection rates per disturbance
- [ ] Five-state machine with LOST coasting, local REACQUIRE, deadline → SEARCH
- [ ] Gimbal never snaps; slew/accel/limits proven by tests
- [ ] Ground truth reaches only metrics/GUI debug overlay (AST + poisoned-truth tests pass)
- [ ] Metrics have explicit status; no fabricated 0/60; verdicts tri-state
- [ ] Benchmarks deterministic, isolated, provenance-complete, GUI-independent
- [ ] GUI thin, benchmark tab non-blocking, no `0` for `None`
- [ ] Validation report generated from real runs, unedited
- [ ] PyInstaller build launches; built CLI benchmark produces valid record
- [ ] `legacy/` deleted; README/docs match reality

## 9. Definition of Done

The project is done when: (1) every phase's acceptance criteria are met and recorded in its report; (2) `pytest -q`, `pytest -m gui`, `ruff check`, and the architecture tests are green; (3) the determinism and isolation tests prove reproducibility; (4) `docs/VALIDATION_REPORT.md` was generated from real benchmark JSON and states honestly which PS requirements are met, failed or not measurable; (5) a standalone executable runs the GUI and CLI benchmark; (6) no ground truth, fabricated default, or global mutable state exists in the tracking path; (7) the legacy JS/Electron/Three.js code and the old Python modules are gone from the repo.

## 10. Open Decisions To Confirm Before Phase 2 (defaults chosen if you don't answer)

1. **Acquisition reference** — default: report both from-start and from-first-observable; requirement evaluated on from-first-observable with declared initial offsets in scenarios.
2. **Tracking error statistic** — default RMS ≤ 10 px (p95 also reported).
3. **"Noise σ ≤ 20 px"** — default interpreted as ≤ 20 grey levels for Gaussian noise.
4. **Multi-target policy** — default: tracker follows nearest-to-prediction/strongest; metrics score the target flagged primary in simulation only.
5. **Field of regard** — default ±10° (reachable within 2 s at 5°/s); tell me if evaluators use a wider search area, because SEARCH-based acquisition ≤ 2 s would then be infeasible at 5°/s.
