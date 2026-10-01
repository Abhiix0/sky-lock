# SkyLock Baseline Audit & Legacy Archive

**Date:** 2026-09-30  
**Phase:** Phase 0 (Repository Cleanup, Baseline & Skeleton)

---

## 1. Initial Python Test Suite Baseline

Before moving legacy files, the existing Python test suite was executed against `src/skylock` using the legacy test harness:

```bash
$env:PYTHONPATH="src"
python -m pytest tests_python -q
```

**Result:**
```
90 passed in 2.08s
```
All 90 unit tests across 10 legacy test files passed.

---

## 2. Legacy Migration Log

All legacy, obsolete, or reference implementations were moved into `legacy/` (never rewritten or deleted; frozen for reference until Phase 12).

### 2.1 `legacy/js/` (JavaScript / Three.js / Electron)
- `src/*.js`: `GLTFSpecGlossExtension.js`, `loadAssets.js`, `main.js`, `orbit.js`, `sceneSetup.js`, `simClock.js`, `ui.js`
- `src/tracking/`: `api.js`, `beacon.js`, `beaconId.js`, `benchmark.js`, `cameraPanel.js`, `candidateTracker.js`, `capture.js`, `charts.js`, `commsConsole.js`, `config.js`, `controller.js`, `decoys.js`, `detector.js`, `disturbancePanel.js`, `disturbances.js`, `exporter.js`, `geometry.js`, `gimbal.js`, `hud.js`, `kalman.js`, `linkLine.js`, `metrics.js`, `observerState.js`, `overlay.js`, `prng.js`, `scanPatterns.js`, `scenarios.js`, `stateMachine.js`, `trackingSystem.js`, `virtualCamera.js`
- `electron/`: Electron entry points and preload scripts
- Configuration & Package Files: `vite.config.js`, `package.json`, `package-lock.json`, `eslint.config.js`, `.prettierrc`, `.prettierignore`, `index.html`
- Tests & Scripts: `tests/*.js` (11 unit/integration test files), `scripts/*.mjs` (`benchmark-to-md.mjs`, `debug-earth-glb.mjs`)
- Static Assets: `public/` (GLB models and assets)

### 2.2 `legacy/python/` (Reference Python Algorithm Modules & Tests)
- `src/skylock/*.py`:
  - `beacon_id.py`
  - `candidate_tracker.py`
  - `config.py`
  - `controller.py`
  - `detector.py`
  - `disturbances.py`
  - `geometry.py`
  - `gimbal.py`
  - `kalman.py`
  - `scan_patterns.py`
  - `state_machine.py`
  - `__init__.py`
- `tests_python/`: 10 legacy test files (`test_beacon_id.py`, `test_candidate_tracker.py`, `test_controller.py`, `test_detector.py`, `test_disturbances.py`, `test_geometry.py`, `test_gimbal.py`, `test_kalman.py`, `test_scan_patterns.py`, `test_state_machine.py`)

### 2.3 `legacy/docs/` (Stale / JS-oriented Documentation)
- `docs/figures/` (including `benchmark.json` and figures)
- `docs/report-draft.md`
- `docs/user-manual-draft.md`
- `docs/BASELINE.md`
- `docs/CLEAN_MACHINE_TEST.md`
- `docs/PS_PARAMS.md`
- `docs/METRICS.md`
- `docs/CONFIG.md`
- `docs/BENCHMARK_SCHEMA.md`

*(Note: `docs/PS_SPEC.md` was preserved in place as the authoritative specification; `docs/MASTER_PLAN.md` established as implementation blueprint).*

---

## 3. Verified Audit Findings (from MASTER_PLAN §0)

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
