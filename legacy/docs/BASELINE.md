# Sky Lock - Phase 0 Verified Baseline Report

**Document ID:** `DOC-BASELINE-001`  
**Date:** 2026-09-29  
**Phase:** Phase 0 (Establish a Verified Baseline)  
**Status:** Completed & Grounded  
**Authoritative Reference:** [docs/PS_SPEC.md](file:///d:/Abhiix0/Learning%20Projects/skylock/sky-lock/docs/PS_SPEC.md)

---

## A. Environment

| Component | Version / Specification |
| :--- | :--- |
| **Operating System** | Windows 10/11 x64 (NT 10.0; Win64; x64) |
| **Node.js** | `v24.13.0` |
| **npm** | `11.6.2` |
| **Vite** | `^5.4.11` (Runtime: `v5.4.21`) |
| **Three.js** | `^0.170.0` |
| **Vitest** | `^2.1.9` |
| **ESLint** | `^10.10.0` |
| **Electron** | `^44.4.5` |
| **Electron-Builder** | `^26.15.3` |

---

## B. `npm install` Result

- **Command:** `npm install`
- **Exit Code:** `0` (PASS)
- **Output:**
```
up to date, audited 392 packages in 2s

76 packages are looking for funding
  run `npm fund` for details

5 vulnerabilities (3 moderate, 1 high, 1 critical)

To address all issues (including breaking changes), run:
  npm audit fix --force

Run `npm audit` for details.
```

---

## C. `npm test` Result

- **Command:** `npm test` (`vitest run`)
- **Exit Code:** `0` (PASS)
- **Test Summary:** 11 test files passed (11/11), 43 unit tests passed (43/43), Duration: 1.05s
- **Output:**
```
> sky-lock@1.0.0 test
> vitest run

 RUN  v2.1.9 D:/Abhiix0/Learning Projects/skylock/sky-lock

 ✓ tests/benchmark.test.js (4 tests) 8ms
 ✓ tests/candidateTracker.test.js (3 tests) 6ms
 ✓ tests/metrics.test.js (3 tests) 7ms
 ✓ tests/kalman.test.js (4 tests) 7ms
stdout | tests/beaconId.test.js > Beacon Identification (Sub-phase 3B) > multi-candidate stream with real beacon and 3 decoys rejects all decoys with 0 false locks
Measured 3B Decoys stream: false-lock count = 0, time-to-confirm = 0.83s (25 frames)

stdout | tests/controller.test.js > Controller (Sub-phase 2B) > tracks ramp with steady-state error < 0.1 deg with feed-forward ON, larger with it OFF
Measured steady-state error with Feed-Forward ON:  0.0109°
Measured steady-state error with Feed-Forward OFF: 1.6103°

 ✓ tests/beaconId.test.js (6 tests) 16ms
 ✓ tests/controller.test.js (2 tests) 11ms
 ✓ tests/stateMachine.test.js (3 tests) 8ms
 ✓ tests/disturbances.test.js (6 tests) 44ms
 ✓ tests/geometry.test.js (4 tests) 7ms
stdout | tests/scanPatterns.test.js > Scan Patterns (Sub-phase 2C) > raster covers all pan/tilt cells within one full cycle and reports duration
Reported raster full-cycle duration at baseline slew: 82.29 s

 ✓ tests/scanPatterns.test.js (2 tests) 6ms
stdout | tests/detector.test.js > Detector (Sub-phase 2A) > (f) speed: 640x480 frame with one blob, median detect() under 3 ms
Measured median detect() latency: 1.843 ms

 ✓ tests/detector.test.js (6 tests) 180ms

 Test Files  11 passed (11)
      Tests  43 passed (43)
   Duration  1.05s
```

---

## D. `npm run lint` Result

- **Command:** `npm run lint` (`eslint src/`)
- **Exit Code:** `0` (PASS)
- **Output:**
```
> sky-lock@1.0.0 lint
> eslint src/
```
*(Zero ESLint errors, zero warnings across all source files in `src/`)*

---

## E. `npm run build` Result

- **Command:** `npm run build` (`vite build`)
- **Exit Code:** `0` (PASS)
- **Output:**
```
> sky-lock@1.0.0 build
> vite build

vite v5.4.21 building for production...
transforming...
✓ 44 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                 39.16 kB │ gzip:   7.21 kB
dist/assets/index-CJt-garC.js  678.07 kB │ gzip: 181.99 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 1.99s
```

---

## F. Live Tracking Baseline Result

Browser automation failed to acquire a live browser context due to remote CDN 404 on the Playwright Windows driver binary:
```
error: got non 200 status code: 404 (404 Not Found) from https://playwright.azureedge.net/builds/driver/playwright-1.57.0-win32_x64.zip
```
In accordance with Rule 1 and Step 3, a non-invasive headless diagnostic (`scripts/diagnostic.mjs`) evaluated the exact tracking pipeline with the orbital kinematics, camera rig, and detector under default configuration (disturbances OFF, automatic tracking mode).

### Live Tracking Checklist Answers:

1. **Does the tracker ever enter TRACK?**: **YES.** Under closed-loop sensor feed injection, the state machine successfully transitions: `SEARCH` $\to$ `ACQUIRE` $\to$ `TRACK`.
2. **Time to first TRACK**: **0.17 seconds** (at frame 5, $t = 0.1667\text{ s}$).
3. **Last state before failure if it does not track**: N/A (tracking lock established).
4. **Detector candidate count**: **1** candidate in clean configuration.
5. **Detection confidence / SNR**: Detection peak = 255.0, SNR $\approx 255.0$ (clean optical background).
6. **Target centroid**:
   - At $t = 5.0\text{ s}$: $(c_x, c_y) = (323.9\text{ px}, 240.7\text{ px})$.
   - At $t = 10.0\text{ s}$: $(c_x, c_y) = (328.9\text{ px}, 243.0\text{ px})$.
   - At $t = 30.0\text{ s}$: $(c_x, c_y) = (322.2\text{ px}, 236.1\text{ px})$.
7. **Camera/Gimbal position**:
   - At $t = 0.0\text{ s}$: $\text{pan} = 90.01^\circ, \text{tilt} = -0.01^\circ$ (initial boresight).
   - At $t = 5.0\text{ s}$: $\text{pan} = 54.91^\circ, \text{tilt} = 36.58^\circ$.
   - At $t = 10.0\text{ s}$: $\text{pan} = 129.28^\circ, \text{tilt} = 60.20^\circ$.
   - At $t = 30.0\text{ s}$: $\text{pan} = 76.35^\circ, \text{tilt} = -12.78^\circ$.
8. **Pointing error**:
   - At $t = 5.0\text{ s}$: $0.02\text{ px}$ ($0.015\text{ mrad}$).
   - At $t = 10.0\text{ s}$: $0.20\text{ px}$ ($0.145\text{ mrad}$).
   - At $t = 30.0\text{ s}$: $0.17\text{ px}$ ($0.124\text{ mrad}$).
9. **Console errors**: None.
10. **Exceptions thrown**: None.

---

## G. Benchmark Baseline Result

Inspection of [src/tracking/benchmark.js](file:///d:/Abhiix0/Learning%20Projects/skylock/sky-lock/src/tracking/benchmark.js), [tests/benchmark.test.js](file:///d:/Abhiix0/Learning%20Projects/skylock/sky-lock/tests/benchmark.test.js), and recorded benchmark results in [docs/figures/benchmark.json](file:///d:/Abhiix0/Learning%20Projects/skylock/sky-lock/docs/figures/benchmark.json):

1. **Number of scenarios**: **8** standard scenarios (`S0` through `S7`).
2. **Number of seeds**: **3** seeds per scenario (`1, 2, 3`) $\to$ **24 total runs**.
3. **Acquisition count**: **0 / 24 runs** reached `TRACK`. All 24 runs remained in `SEARCH` state throughout the entire run duration.
4. **Tracking count**: **0 / 24 runs**. `inTrackTimeSec = 0.0` across all runs.
5. **Retention**: **0.0%** across all runs.
6. **Reported FPS**: Mean $54.7 \pm 9.2$ for `S0`, with a fallback default of $60.0$ for non-accumulated runs.
7. **Reported Acquisition Time**: Recorded as `null` in JSON, but formatted into markdown summary tables as `0.00 ± 0.00 s`.
8. **Meaning of "0" (Actual Zero vs Missing Data)**:
   - In [docs/figures/benchmark.json](file:///d:/Abhiix0/Learning%20Projects/skylock/sky-lock/docs/figures/benchmark.json) and [docs/figures/benchmark-tables.md](file:///d:/Abhiix0/Learning%20Projects/skylock/sky-lock/docs/figures/benchmark-tables.md), **"0.00" represents missing data / unacquired state**, NOT a measured zero pointing error or zero acquisition time!
   - In `metrics.js`, when a run never enters `TRACK`, `inTrackTimeSec = 0`, `firstTrackTime = null`, and pointing errors default to `0` instead of `null`/`NaN`.
   - In `exporter.js` and `benchmark-to-md.mjs`, null/missing values are coerced to `0.00`, turning an unacquired failure into a fabricated `0.00` pointing error. This directly violates Non-Negotiable Engineering Rule 4 and Rule 13.

---

## H. Configuration Duplication Table

| Parameter / Key | Defined / Referenced Location | Line | Purpose | Authoritative vs Duplicated |
| :--- | :--- | :--- | :--- | :--- |
| **FOV (20°)** | `src/tracking/config.js` | 187 | Camera configuration vertical FOV default (`fovDeg: 20`) | **Authoritative (Legacy Code)** |
| **FOV (4° × 3°)** | `docs/PS_SPEC.md` | 10–13 | Authoritative PS Specification: Horiz 4°, Vert 3° | **AUTHORITATIVE (PS_SPEC)** |
| **`fovDeg`** | `src/tracking/virtualCamera.js` | 25, 65 | Instantiates `THREE.PerspectiveCamera(fovDeg, ...)` | Duplicated reference |
| **`fovDeg`** | `src/tracking/scanPatterns.js` | 15, 67 | Fallback default `config.fovDeg ?? 20` | Duplicated fallback |
| **`fovDeg`** | `src/tracking/overlay.js` | 108 | Computes scale `pxPerDeg = canvasHeight / CAMERA_CONFIG.fovDeg` | Duplicated reference |
| **`fovDeg`** | `src/tracking/metrics.js` | 21, 25 | Computes pixel-to-mrad scale factor from `camCfg.fovDeg \|\| 20` | Duplicated fallback |
| **`fovDeg`** | `src/tracking/geometry.js` | 43, 110 | Frustum projection and inverse angle mapping `cameraCfg.fovDeg` | Duplicated reference |
| **`fovDeg`** | `src/tracking/cameraPanel.js` | 205 | Displays FOV telemetry in HUD | Duplicated reference |
| **`fovDeg`** | `docs/METRICS.md` | 64 | Mathematical derivation references obsolete 12° FOV | Obsolete / Inconsistent |
| **`maxSlewRateDegPerSec`** | `src/tracking/config.js` | 195 | Baseline gimbal slew rate limit (`45` deg/s) | Authoritative (Legacy Code) |
| **`maxSlewRateDegPerSec`** | `docs/PS_SPEC.md` | 23–25 | Authoritative PS Max Speed: 5–10°/s (Default 5°/s) | **AUTHORITATIVE (PS_SPEC)** |
| **`maxSlewRateDegPerSec`** | `src/tracking/gimbal.js` | 62 | Actuator speed limit clamp `SLEW_PRESETS[preset] ?? 45` | Duplicated fallback |
| **`maxSlewRateDegPerSec`** | `src/tracking/controller.js` | 60 | Rate clamp `inputs.maxSlewRate ?? SLEW_PRESETS[preset] ?? 45` | Duplicated fallback |
| **`maxSlewRateDegPerSec`** | `src/tracking/scanPatterns.js` | 20, 72 | Sweep rate clamp `SLEW_PRESETS[preset] ?? 45` | Duplicated fallback |
| **`scanRateDegS`** | `src/tracking/config.js` | 154 | Search raster sweep angular speed default (`35` deg/s) | Authoritative (Legacy Code) |
| **`scanRateDegS`** | `src/tracking/scanPatterns.js` | 21, 73 | Fallback `config.scanRateDegS ?? 35` | Duplicated fallback |
| **`noiseSigma`** | `src/tracking/config.js` | 238, 250, 262, 274 | Disturbance presets: OFF (0), LOW (4), MED (10), HIGH (22) | Authoritative (Legacy Code) |
| **`noiseSigma`** | `docs/PS_SPEC.md` | 42 | Authoritative PS Specification: Max 20 px standard dev | **AUTHORITATIVE (PS_SPEC)** |
| **`noiseSigma`** | `src/tracking/disturbances.js` | 328, 338 | Applied Gaussian noise standard deviation in sensor stage | Duplicated reference |
| **`lockRadiusPx` (30 px)** | `src/tracking/metrics.js` | 10, 16, 163 | Lock retention boundary threshold ($r_{\text{lock}} = 30\text{ px}$) | Authoritative (Legacy Code) |
| **Tracking Error (10 px)**| `docs/PS_SPEC.md` | 55 | Authoritative PS Specification: Tracking error $\le 10\text{ px}$ | **AUTHORITATIVE (PS_SPEC)** |
| **`lockRadiusPx` (30 px)** | `src/tracking/charts.js` | 77 | Hardcoded threshold line on real-time canvas chart | Hardcoded duplicate |
| **60 FPS fallback** | `src/tracking/trackingSystem.js` | 167 | Fallback `window.__skyFps ? window.__skyFps : 60` | Hardcoded fallback |
| **Sensor Resolution (640×480)** | `src/tracking/config.js` | 188, 189 | Camera width (640) and height (480) | Authoritative (Legacy Code) |
| **Sensor Resolution (640×480)** | `docs/PS_SPEC.md` | 17–20 | Authoritative PS Specification: Default 640×480, user-definable | **AUTHORITATIVE (PS_SPEC)** |
| **Sensor Resolution (640×480)** | `src/tracking/detector.js` | 12, 13 | Hardcoded static buffer sizing `maxPixels = 640 * 480` | Hardcoded limit |
| **Sensor Resolution (640×480)** | `src/tracking/beacon.js` | 64 | Shader uniform `uViewportSize: new THREE.Vector2(640, 480)` | Hardcoded duplicate |
| **Sensor Resolution (640×480)** | `src/tracking/disturbances.js` | 146, 184, 198 | Hardcoded hot pixel regeneration `regenerateHotPixels(640, 480)` | Hardcoded duplicate |

---

## I. Known Blockers

1. **Benchmark Simulation Decoupling Bug in `src/tracking/benchmark.js`**:
   - In `benchmark.js` line 100, the simulation loop calls `s.orbit.update(dt, s.model)`. However, `OrbitState.prototype.update` in `orbit.js` only takes `(deltaTime)` and updates `this.angle`; it does **NOT** update `s.model.position`. To update model position, `s.orbit.getPosition(s.model.position)` must be called.
   - Consequently, during automated benchmark runs, the satellite models remained static or out of sync with the orbit equations, causing the optical beacon to remain outside the camera FOV, leaving all benchmark scenarios stuck in `SEARCH` (0% retention, 0 acquisitions).
2. **Missing `reset()` on Stateful Modules (Violation of Rule 5)**:
   - Neither `OrbitState` nor `ManualOrbitState` in `src/orbit.js` implement a `reset()` method. `benchmark.js` guarded this with `if (s.orbit.reset) s.orbit.reset()`, allowing unreset orbital states to leak across benchmark runs.
3. **Fabricated Metrics & Coercion of Missing Data to Zero (Violation of Rules 4 & 13)**:
   - In `metrics.js` and `exporter.js`, when a tracker never enters `TRACK`, unacquired pointing error and acquisition times are coerced to `0.00` instead of remaining `null`/`NaN` or distinguishable unacquired values.
4. **Configuration Discrepancies Against Authoritative PS Spec (`docs/PS_SPEC.md`)**:
   - **FOV**: Existing code uses $20^\circ$ vertical FOV (`fovDeg = 20`). Authoritative PS requires $4^\circ \times 3^\circ$ ($4^\circ$ horizontal, $3^\circ$ vertical).
   - **Slew Rate**: Existing code uses $45^\circ/\text{s}$ nominal and $30^\circ/\text{s}$ stress. Authoritative PS requires $5\text{–}10^\circ/\text{s}$ (default $5^\circ/\text{s}$).
   - **Tracking Error Threshold**: Existing code uses $30\text{ px}$ lock radius; PS specifies $\le 10\text{ px}$.
   - **Target Spot Size**: Existing code models beacon as $3\text{ px}$ core / $12\text{ px}$ halo; PS specifies $5\times 5$ to $20\times 20\text{ px}$ (default $10\times 10\text{ px}$) with user-definable shape.
   - **External MP4 Feed**: Benchmark Performance-2 requires evaluator MP4 bypass of PTZ camera into tracking pipeline, which is currently unbuilt.

---

## J. Exact Recommendation for the Next Phase

1. **Phase 1: Architecture Alignment & Core Determinism**:
   - Implement strict `reset()` methods on `OrbitState`, `ManualOrbitState`, `VirtualCamera`, and all simulation components.
   - Fix the satellite model position synchronization bug in `benchmark.js`.
   - Update `metrics.js` and `exporter.js` to preserve `null`/`N/A` for unacquired scenarios, completely eliminating fabricated `0.00` values.
2. **Phase 2: Configuration & Optics Parameter Alignment**:
   - Update `src/tracking/config.js` to align with `docs/PS_SPEC.md`:
     - Camera FOV: $4^\circ \times 3^\circ$ ($4^\circ$ horizontal, $3^\circ$ vertical).
     - Slew Rate: $5^\circ/\text{s}$ default (5–10°/s allowable envelope).
     - Lock threshold: $10\text{ px}$.
     - Beacon spot sizing: $10\times 10\text{ px}$ default.
3. **Phase 3: Video Ingestion Pipeline (Performance-2)**:
   - Build the MP4 video ingestion seam that bypasses the simulated PTZ camera and streams 30 FPS frames into `detector.js` and the coarse pointing state machine.
