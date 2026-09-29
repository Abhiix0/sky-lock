# Sky Lock: Phased Plan and Prompts

Based on a read of `sky-lock-main.zip` (all of `src/`, `index.html`, config) plus a Python simulation of the orbit maths in `orbit.js`. I have **not** run the app in a browser, so treat the "already works" claims as "the code looks complete", and verify them with the Phase 1A checklist.

---

## 1. What the codebase already has

| Area | Status |
| --- | --- |
| Earth, 2 satellites, orbits, ISL beam, comms console, Auto/Manual modes | Done, leave alone |
| `config.js` (FOV 20°, 640×480, 30 Hz feed, ±180° pan, ±90° tilt, 30°/s slew) | Done, but `maxSlewRateDegPerSec` is **not used by anything** |
| `virtualCamera.js` gimbal rig, offscreen render target, `getFrame()`, `getGroundTruthDirection()` | Done (this is your sub-phase 1A) |
| `cameraPanel.js` PiP + crosshair + telemetry + buttons | Done |
| Beacon on S-2 | **Missing** (1B) |
| Slew/accel clamping, fixed timestep, `setGimbalCommand` | **Missing** (1C). `main.js` still has a "TEMPORARY DEBUG CONTROLS" arrow-key block |
| Tests, git history | None. The zip has no `.git`, so run `git init` first |

## 2. Findings that change the plan

These come from the code and from simulating the orbit formulas (1× speed, sim seconds):

1. **Occlusion is frequent and predictable.** S-1 to S-2 distance ranges 6 to 46 units. Earth blocks the line of sight about 20% of the time. The run **starts occluded** (first \~6 s), then \~50 s clear, \~12 s blocked, repeating every \~63 s. This is good for demoing LOST/REACQUIRE, and it means the tracker starts in SEARCH.
2. **Constant-velocity coasting cannot bridge an occlusion.** After a 12 s blackout the predicted position is off by about **27° pan / 22° tilt**, which is larger than the camera's field of view. REACQUIRE therefore needs an expanding search around the prediction (radius up to \~45°), not just "point at the Kalman estimate".
3. **30°/s slew is slightly too slow.** The line of sight in S-1's body frame peaks at \~36°/s pan (95th percentile 27°/s). At 30°/s you lose lock for \~4% of the visible time. Plan: default 45°/s for the baseline and keep 30°/s as a "PS stress" preset, unless your PS table forces 30.
4. **Pan sweeps the full ±180° and crosses the seam.** The controller and gimbal must handle angle wrap (shortest path), or the camera spins 358° to follow a 2° change.
5. **S-2's model is huge in the feed.** At 20° FOV the 4-unit satellite covers \~130 to 900 px, dwarfing a fixed-pixel beacon. Decision: hide S-2's body in the feed by default (point-source beacon, like a real FSOC link) with a config flag to bring it back as clutter.
6. **Frame rate leaks into the simulation.** `sat.model.quaternion.slerp(_targetQuat, 0.25)` is per rendered frame, and orbit updates use variable `deltaTime`. Results change with FPS, so a seeded benchmark cannot be reproducible until this is fixed (1C-1).
7. **Image convention trap.** `readRenderTargetPixels` returns rows bottom-up (the PiP flips it), while `getGroundTruthDirection` returns pixel coordinates with a top-left origin. The detector must convert once, at its input.
8. **Electron blockers:** `loadAssets.js` fetches the DRACO decoder from `gstatic.com` (none of the 3 GLBs use Draco, I checked, so it can simply be removed), and assets use absolute `/assets/...` paths that break under `file://`.
9. **Missing input:** I don't have your **PS parameter table**. Send it and Prompt 0 maps it into `config.js`.

## 3. Roadmap

Commit after every prompt. If the agent drifts, `git checkout -- .` and re-run with a tighter prompt.

| # | Prompt | Outcome | Effort |
| --- | --- | --- | --- |
| 0 | Baseline and PS params | git, lint clean, PS table in config | S |
| 1A | *(done, verify only)* | Camera rig and PiP | - |
| 1B | Beacon | Fixed-pixel beacon visible in feed, hidden by Earth | M |
| 1C-1 | Fixed-timestep sim clock | Deterministic, FPS-independent sim | M |
| 1C-2 | Gimbal servo and manual control | Slew/accel-limited motion, clean API | M |
| 2A | Detector | Beacon centroid from pixels | M |
| 2B | Kalman and controller | Prediction, PID plus feed-forward | L |
| 2C | State machine and scan | SEARCH/ACQUIRE/TRACK/LOST/REACQUIRE | L |
| 2D | Integration and overlay | Closed loop with bbox/crosshair/state | M |
| 3A | Disturbances | Turbulence, vibration, noise, blur, drops | L |
| 3B | Decoys and blink ID | Multi-target, code correlation | L |
| 3C | Metrics and HUD | Numbers and live charts | M |
| 3D | Scenarios and benchmark | Seeded runs, JSON/CSV export | M |
| 4A | Electron packaging | Standalone exe | M |
| 4B | Polish and code hygiene | Clean, commented source | M |
| 4C | Evidence and doc drafts | Screenshots, tables, report and manual drafts | M |
| 4D | Demo mode and submission zip | Video script, final package | S |

---

## 4. Preamble (paste at the top of EVERY prompt)

If your tool supports a project rules file, put this there instead.

```text
PROJECT CONTEXT
Sky Lock: Vite + Three.js r170, vanilla JS ES modules (no framework, no TypeScript).
S-1 (observer, orbit r=20, 25 deg) and S-2 (target, orbit r=26, 65 deg) orbit Earth (radius 10).
S-1 carries a virtual pan/tilt gimbal camera (src/tracking/virtualCamera.js, settings in
src/tracking/config.js) rendering to a 640x480 offscreen target shown in a PiP panel
(src/tracking/cameraPanel.js). The project goal is FSOC-style beacon acquisition and tracking:
detect S-2's beacon in rendered pixels, Kalman-track it, steer the gimbal with PID plus
feed-forward, run a state machine, add disturbances, metrics and a benchmark, then package in Electron.

CONVENTIONS (do not deviate)
- Angles in degrees. Pan positive turns toward body +X (toward Earth for S-1); tilt positive is up.
  pan = atan2(x, -z), tilt = atan2(y, hypot(x, z)) in the rig frame, exactly as in getGroundTruthDirection().
- Image coordinates: origin TOP-LEFT, x right, y down, in feed pixels. NOTE the raw frame.data from
  readRenderTargetPixels is BOTTOM-UP (row 0 = bottom). Convert exactly once, at the consumer's input.
- Time: simulation seconds (not wall-clock) for everything except performance measurements.
- Camera sits CAMERA_OFFSET_Z=2.5 units in front of the gimbal pivot on the boresight; ignore the
  parallax except where a prompt says otherwise.

RULES
1. Only create or modify files listed under FILES YOU MAY TOUCH. If another file needs a change,
   stop and tell me instead of editing it.
2. No refactors, renames, reformatting or "cleanup" of existing code beyond the lines the task needs.
3. Must keep working: ISL beam (linkLine.js), comms console, Automatic/Manual satellite modes and
   drag-and-drop placement, speed 1x/2x/4x and pause, the existing PiP panel and buttons.
4. No new runtime dependencies unless the prompt says so. JSDoc on every export.
5. No per-frame allocations in hot paths (reuse Vector3s and typed arrays). No per-frame console.log.
6. Every tunable lives in src/tracking/config.js. No magic numbers in modules.
7. When finished: run `npm run lint` and `npm run build`, fix problems in files you touched, then
   report (a) files changed, (b) exactly how I can verify by hand, (c) anything you were unsure about.
   Do NOT git commit.
```

---

## Phase 0: Baseline

### Prompt 0: Baseline and PS parameter mapping

Before this, run in a terminal: `git init && git add -A && git commit -m "baseline: sub-phase 1A"`. Then paste your PS parameter table into the marked spot.

```text
[PASTE PREAMBLE]

TASK: Establish a clean baseline and map the official PS parameters into config.

FILES YOU MAY TOUCH: src/tracking/config.js, docs/PS_PARAMS.md (new), package.json (scripts only).

1. Run `npm install`, `npm run lint`, `npm run build`. Report failures. Fix only trivial lint errors
   inside files listed above; for anything else, list it and stop.
2. Below is the official PS parameter table:
   <<< PASTE PS TABLE HERE >>>
   Create docs/PS_PARAMS.md with columns: PS parameter | value | config key | status
   (implemented / not yet / not applicable).
3. In config.js, add every PS value that maps to an existing key (fov, resolution, feed rate, pan/tilt
   limits, slew rate). Where the PS value differs from the current default, change the default and
   leave a one-line comment "PS: <name>". Do not remove existing keys.
4. Extend CAMERA_CONFIG with these NEW keys (defaults in parentheses), each with a JSDoc line:
   maxSlewAccelDegPerSec2 (120), panWrap (true), simStepHz (120), maxFeedFramesPerRender (2).
5. Add `export const SLEW_PRESETS = { baseline: 45, ps: <PS slew or 30> }` with a comment explaining
   baseline exists because peak line-of-sight rate is ~36 deg/s.

ACCEPTANCE: app behaves exactly as before; lint and build pass; docs/PS_PARAMS.md lists every PS row.
```

---

## Phase 1: Sensing foundation

### 1A: Camera rig and feed (already implemented, verify by hand)

Open the app and tick these off. If any fail, tell me and I'll write a fix prompt.

- PiP shows the view from S-1, and the S-1 body, ISL beam, orbit lines are not visible in it.
- **AIM S-2** points the crosshair at S-2 (only works when the line of sight is clear).
- Arrow keys nudge pan/tilt, and pan wraps or clamps sensibly at the limits.
- ISL beam, comms console, Manual mode and speed/pause still work.
- No console errors, \~60 FPS main view.

### Prompt 1B: Beacon

```text
[PASTE PREAMBLE]

TASK: Add a beacon on S-2 that appears as a fixed-pixel-size glow in the S-1 camera feed only.

FILES YOU MAY TOUCH: src/tracking/beacon.js (new), src/tracking/config.js,
src/tracking/virtualCamera.js (minimal), src/main.js (only the lines wiring the beacon).

1. config.js: add BEACON_CONFIG = { enabled: true, color: 0xff2bd6 (saturated magenta), coreRadiusPx: 3,
   haloRadiusPx: 12, brightness: 1.0, blinkHz: 0 (0 = steady), blinkDuty: 0.5,
   hideTargetBodyInFeed: true, showMarkerInMainView: false }.
   Why magenta: Earth is blue/green/white, so a chroma metric (min(R,B) - G) separates it from clouds.
2. beacon.js: createBeacon(scene) returns { update(targetSat, simTimeSec), setEnabled, setBrightness,
   setBlink(hz, duty), object }.
   - Implement as THREE.Points with a small custom ShaderMaterial: round soft falloff (bright near-white
     core, colored halo), additive blending, sizeAttenuation OFF so size is in pixels regardless of
     range, depthTest ON (so Earth hides it), depthWrite OFF, high renderOrder.
   - Read gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE) and clamp/warn if haloRadiusPx*2 exceeds it.
   - Do NOT parent it to the satellite model (scaled). Copy the target's world position each update,
     like virtualCamera.js does for the rig.
   - Blink: on = ((simTimeSec * blinkHz) % 1) < blinkDuty, using sim time, never wall-clock.
     Note feed is 30 Hz, so blinkHz above ~7 will alias.
3. Visibility: put the beacon on THREE layer BEACON_LAYER (1). Enable that layer on the feed camera only
   (cam.layers.enable(1)); the main camera must not see it. If showMarkerInMainView is true, add a small
   clearly-styled ring marker visible only to the main camera.
4. virtualCamera.js (minimal edits): enable the beacon layer on `cam`; in the existing hide-list logic,
   also hide the target satellite model during the feed render when hideTargetBodyInFeed is true.
   If it is false, offset the beacon 2.5 units toward the observer so it is not buried in the mesh.
5. main.js: create the beacon after the virtual camera, call beacon.update() each frame for the
   CAMERA_CONFIG.targetId satellite among the active ones (hide if that satellite is not visible/active).
   Use performance.now()/1000 as a stand-in simTime for now; a later prompt will supply real sim time.

ACCEPTANCE (1x speed, from page load):
- First ~6 s: no blob in PiP (Earth is between the satellites). After ~7 s click AIM S-2: a bright
  magenta blob sits at the crosshair.
- The blob stays the same pixel size while distance varies (6 to 46 units over an orbit).
- The blob vanishes around t=57 s to 69 s and again every ~63 s, matching the comms console
  "OBSTRUCTED" status.
- Setting blinkHz=2 in config makes it toggle visibly. Main 3D view shows no beacon.
- ISL beam and everything else unchanged; no console errors.
Commit message: "1B: beacon"
```

### Prompt 1C-1: Fixed-timestep simulation clock

This is the riskiest edit to `main.js`, so it gets its own prompt.

```text
[PASTE PREAMBLE]

TASK: Make the simulation deterministic and independent of rendering FPS.

FILES YOU MAY TOUCH: src/simClock.js (new), src/main.js (animate loop and satellite/earth update
lines only), src/tracking/virtualCamera.js (update/feed cadence only), src/tracking/beacon.js
(only to accept real simTime), src/tracking/config.js.

Current problems: orbits advance with variable deltaTime; `sat.model.quaternion.slerp(_targetQuat, 0.25)`
is applied per rendered frame; virtualCamera.update() paces the feed with performance.now().

1. simClock.js: createSimClock({ stepHz }) with
     advance(realDtSec, timeScale, onStep)   // accumulator; calls onStep(fixedDt) 0..N times
     getSimTime()                            // seconds, monotonic, advances only in fixed steps
     reset()
   Guard against the spiral of death: cap at 16 steps per call and discard the excess.
   timeScale = 0 when paused, else simulationSpeed (existing ui.js exports). Per-satellite
   individualSpeed and individual pause keep working exactly as now.
2. main.js: move orbit stepping, Earth rotation and satellite orientation into the onStep callback.
   Replace the fixed 0.25 slerp with time-based smoothing:
   alpha = 1 - exp(-dt / SAT_ORIENT_SMOOTH_TAU_SEC), add that constant (default 0.05) to config.js.
   Keep the ISL line and comms console updates per rendered frame (visual only).
3. virtualCamera.js: split update() into syncRig(observerSat) (copies pose, cheap) and
   renderFeed(observerSat, simTimeSec) (renders and reads pixels when simTime >= nextFeedTime, then
   nextFeedTime += 1/feedRateHz; if more than maxFeedFramesPerRender are due in one render frame,
   skip the rest and count them in a droppedFeedFrames counter). Keep update() as a thin wrapper so
   nothing else breaks. Call syncRig and renderFeed from onStep so the frame always matches the
   simulation state at that instant.
4. cameraPanel: only re-blit when frame.frameId changed.
5. Expose window.__sky = { getSimTime, getSatellitePositions() } (positions of S-1 and S-2) for testing.
6. Beacon: pass the real simTime.

ACCEPTANCE:
- With DevTools CPU throttling at none and at 6x, `__sky.getSatellitePositions()` sampled at
  getSimTime() >= 30 differ by less than 1e-4 units.
- Speed 2x and 4x still work and pause freezes both orbits and the feed clock.
- Beacon blink period is correct in sim time (pauses when paused).
- Main view >= 55 FPS at 1x, >= 30 FPS at 4x; no console errors; ISL and comms console unchanged.
Commit message: "1C-1: fixed-timestep sim clock"
```

### Prompt 1C-2: Gimbal servo, manual control and Phase-2 API

```text
[PASTE PREAMBLE]

TASK: Add a physically limited gimbal servo, proper manual control, and the clean interface that
Phase 2 will plug into.

FILES YOU MAY TOUCH: src/tracking/gimbal.js (new), src/tracking/api.js (new),
src/tracking/config.js, src/tracking/cameraPanel.js (callback wiring only),
src/main.js (replace the TEMPORARY DEBUG CONTROLS block and wire the gimbal into onStep).

1. gimbal.js: createGimbal(virtualCamera, config) returns
     setGimbalCommand(panDeg, tiltDeg)          // angle setpoint, go-to mode
     setGimbalRateCommand(panRateDegS, tiltRateDegS)   // rate mode
     step(dt)                                   // called from the fixed-step onStep
     getGimbalState()  // { panDeg, tiltDeg, panRateDegS, tiltRateDegS, mode, atLimitPan, atLimitTilt }
     snapTo(panDeg, tiltDeg)                    // debug only, instant
   Dynamics per axis: velocity limited to the active slew preset (config), acceleration limited to
   maxSlewAccelDegPerSec2. Go-to mode uses desiredVel = sign(err)*min(vmax, sqrt(2*a*|err|)) then
   accel-limits the change in velocity (no overshoot). Apply the result with virtualCamera.setPanTilt.
   Pan: if panWrap is true, treat pan as an angle on a circle (error = shortest signed path, state kept
   in (-180,180]); if false, hard-clamp to +/-panLimitDeg. Tilt always hard-clamps.
2. Manual control: hold ArrowLeft/Right/Up/Down to command rates (+/- manualRateDegS, add to config,
   default 20; Shift doubles). Releasing decelerates at the accel limit. Ignore keys when focus is in
   an input/textarea. Existing on-screen buttons keep their IDs: nudges become relative go-to commands,
   AIM S-2 becomes a slew-limited go-to using getGroundTruthDirection (still fine as a manual aid),
   EARTH and RESET likewise.
3. api.js: createTrackingApi({ virtualCamera, gimbal, simClock, getTargetSat }) returns
     getFrame()                    // latest feed frame {width,height,data,timestamp,frameId}
     setGimbalCommand(pan, tilt)
     setGimbalRateCommand(pr, tr)
     getGimbalState()
     getGroundTruth()              // wraps getGroundTruthDirection(target)
     getSimTime()
   Full JSDoc typedefs. Phase 2 must only talk to this module.
4. Add a slew preset switch in config (SLEW_PRESETS from Prompt 0), default 'baseline'.
5. Dev self-test window.__sky.selfTestGimbal(): commands a 90 deg pan step and a 179 -> -179 seam
   crossing, and returns { maxRate, maxAccel, overshootDeg, seamPathDeg } (seam path must be about 2).

ACCEPTANCE:
- selfTestGimbal: maxRate <= slew limit, maxAccel <= accel limit, overshoot < 0.05 deg, seamPathDeg ~ 2.
- Holding an arrow key ramps smoothly, never exceeds the limit, and stops smoothly on release.
- Stable 60 FPS, no console errors, old debug key block is gone, ISL/comms/Manual mode unchanged.
Commit message: "1C-2: gimbal servo, manual control, tracking API"
```

---

## Phase 2: Detection and tracking

### Prompt 2A: Detector

```text
[PASTE PREAMBLE]

TASK: Detect the beacon in a feed frame and return blob centroids. Pure module, no THREE, no DOM.

FILES YOU MAY TOUCH: src/tracking/detector.js (new), src/tracking/config.js,
tests/detector.test.js (new), package.json (add devDependency `vitest` and script "test").

1. config.js: DETECTOR_CONFIG = { mode: 'chroma' | 'luma' (default 'chroma'), lumaThreshold: 200,
   chromaThreshold: 90, minAreaPx: 2, maxAreaPx: 900, maxBlobs: 8, roiMarginPx: 40 }.
   chroma score per pixel = min(R, B) - G (beacon is magenta; clouds and ocean score near 0).
2. detector.js: createDetector(config) returns detect(frame, opts?) where opts.roi = {x,y,w,h} optional.
   Returns { blobs: [{ cx, cy, area, peak, snr, bbox:{x0,y0,x1,y1} }], processingMs }.
   - Input frame.data is RGBA bottom-up; output coordinates are top-left origin with subpixel
     intensity-weighted centroids.
   - Pass 1: collect indices of pixels above threshold into a preallocated Int32Array (sparse).
     Pass 2: connected components (4-connectivity) via union-find on those pixels only.
   - Per blob: area, peak score, weighted centroid, bbox, snr = (peak - bgMean)/max(bgStd, 1) with the
     background estimated from a subsample of ~1% of pixels.
   - Reject blobs outside [minAreaPx, maxAreaPx]. Sort by peak descending.
   - Preallocate all buffers from frame size; zero allocations per call in steady state.
3. tests/detector.test.js (vitest, node environment): synthetic frames built in the test:
   (a) single Gaussian magenta blob at a known subpixel position: centroid error < 0.2 px;
   (b) a large white "cloud" region plus the blob: only the blob is returned in chroma mode;
   (c) empty black frame: zero blobs; (d) two blobs: both returned, stronger first;
   (e) row-order check: a blob near the TOP of the image must come back with small y.
   (f) speed: 640x480 frame with one blob, median detect() under 3 ms.
4. Dev hook only: in main.js do NOT wire it yet.

ACCEPTANCE: `npm test` passes; lint and build pass. Report the measured median ms for test (f).
Commit message: "2A: detector"
```

### Prompt 2B: Kalman tracker and gimbal controller

```text
[PASTE PREAMBLE]

TASK: Convert detections into a smoothed line-of-sight estimate, and steer the gimbal with PID plus
feed-forward. Pure modules with unit tests.

FILES YOU MAY TOUCH: src/tracking/geometry.js (new), src/tracking/kalman.js (new),
src/tracking/controller.js (new), src/tracking/config.js, tests/geometry.test.js, tests/kalman.test.js,
tests/controller.test.js (all new).

1. geometry.js:
   pixelToBodyAngles(px, py, panDeg, tiltDeg, cameraCfg) -> { panDeg, tiltDeg }
     Build the ray in camera space from the pixel using fovDeg/width/height (pinhole, square pixels), then
     rotate by the gimbal: derive the order from virtualCamera.js (panGroup.rotation.y = -pan,
     tiltGroup.rotation.x = +tilt, camera looks down -Z), and return body-frame pan/tilt with the
     conventions in the Preamble.
   bodyAnglesToPixel(...) the inverse. wrapDeg(a) -> (-180,180]. angularDiffDeg(a,b) shortest signed.
   Test: for random gimbal angles and pixels, the round trip error < 1e-6 deg; and a pixel at image
   centre returns exactly the gimbal angles.
2. kalman.js: constant-velocity filter on state [pan, tilt, panRate, tiltRate] in body-frame degrees.
   API: init(measPan, measTilt, t), predict(t), update(measPan, measTilt, t), getState(),
   getPredicted(t), getInnovationGate(measPan, measTilt) (Mahalanobis distance), getPositionSigmaDeg().
   Pan handling: keep the filter state UNWRAPPED and unwrap each measurement relative to the prediction
   so the +/-180 seam does not create a jump. Process noise and measurement noise in config
   (KALMAN_CONFIG: qAccelDegS2, rMeasDeg). Covariance must grow during prediction-only coasting.
   Tests: converges on a constant-rate target; survives seam crossing; sigma grows while coasting;
   a 5-sigma outlier is rejected by the gate.
3. controller.js: createController(cfg) with step(dt, {gimbalPanDeg, gimbalTiltDeg, losEstimate,
   losRateEstimate, mode}) -> { panRateDegS, tiltRateDegS }.
   Per axis: error = angularDiff(losEstimate, gimbalAngle); output = Kp*e + Ki*integral(e) + Kd*filtered
   d(e)/dt + Kff*losRateEstimate. Anti-windup by conditional integration and clamp, derivative low-pass
   filter, output clamp at the slew limit. CONTROLLER_CONFIG holds every gain with a starting guess
   (Kp 4, Ki 0.5, Kd 0.2, Kff 1.0). It commands RATES, to be fed to gimbal.setGimbalRateCommand.
   Test with a tiny first-order simulated gimbal (no THREE): tracks a ramp with steady-state error
   under 0.1 deg with feed-forward on, larger with it off; no windup after 5 s of saturation.

ACCEPTANCE: npm test passes; lint/build pass. Report the two steady-state errors from the controller test.
Commit message: "2B: geometry, kalman, controller"
```

### Prompt 2C: State machine and scan patterns

```text
[PASTE PREAMBLE]

TASK: Implement the tracking state machine with search and reacquire patterns. Pure module, unit tested.

FILES YOU MAY TOUCH: src/tracking/stateMachine.js (new), src/tracking/scanPatterns.js (new),
src/tracking/config.js, tests/stateMachine.test.js, tests/scanPatterns.test.js (new).

Context you must design around (measured): the beacon is unobservable for ~12 s per ~63 s orbit cycle.
A constant-velocity prediction across that gap is off by ~27 deg pan / ~22 deg tilt, which exceeds the
field of view (20 deg vertical, ~26.7 deg horizontal). So REACQUIRE must sweep around the prediction.

1. scanPatterns.js (pure functions returning the next pan/tilt setpoint from elapsed time):
   raster(elapsed, cfg): sweeps pan continuously around 360 deg in rows whose spacing is
   FOV * (1 - overlap), covering tilt within +/- tiltScanLimitDeg (config, default 55), at
   scanRateDegS <= current slew limit. Rows alternate direction.
   spiral(elapsed, center, cfg): expanding Archimedean spiral around `center` with radial pitch
   FOV * (1 - overlap), out to reacquireMaxRadiusDeg (default 45), then reports `done`.
2. stateMachine.js: createStateMachine(cfg, deps). Inputs each detection frame:
   { simTime, detections, kalman, gimbalState }. Outputs { state, setpoint or rateCommand mode,
   selectedDetection, events }.
   States and transitions (all thresholds in TRACKING_CONFIG):
   - SEARCH: no track. Run raster. Any detection above SNR gate -> ACQUIRE.
   - ACQUIRE: stop scanning, center the candidate. acquireConfirmFrames (3) consecutive detections
     inside the gate -> TRACK (initialize Kalman). If lost for acquireTimeoutSec -> SEARCH.
   - TRACK: gate detections with the Kalman innovation gate; update the filter; if more than
     lostMissFrames (5) consecutive misses -> LOST.
   - LOST: coast on the Kalman prediction with feed-forward. If a gated detection appears ->
     TRACK. After coastMaxSec (14) -> REACQUIRE.
   - REACQUIRE: run spiral around the last predicted position. Any detection -> ACQUIRE. When the
     spiral is done -> SEARCH.
   Emit events {type:'STATE_CHANGE', from, to, simTime, reason} for the metrics module later.
   It must never depend on wall-clock time.
3. Tests with scripted detection sequences: clean acquisition; drop-out shorter than the coast window
   resumes TRACK; a 12 s blackout goes TRACK -> LOST -> REACQUIRE -> ACQUIRE -> TRACK when a detection
   reappears inside the spiral; raster covers all pan/tilt cells within one full cycle (assert coverage).

ACCEPTANCE: npm test passes; lint/build pass. Report the raster full-cycle duration at the baseline
slew preset.
Commit message: "2C: state machine and scan patterns"
```

### Prompt 2D: Integration and overlay (closed loop goes live)

```text
[PASTE PREAMBLE]

TASK: Wire detector, Kalman, controller and state machine into the live app through the tracking API,
and draw the overlay.

FILES YOU MAY TOUCH: src/tracking/trackingSystem.js (new), src/tracking/overlay.js (new),
src/tracking/cameraPanel.js (add overlay hook and a mode toggle), src/main.js (create the system,
call it from onStep, add toggle wiring), index.html (add ONE small Tracking AUTO/MANUAL toggle inside the
existing gimbal panel, matching existing styles), src/tracking/config.js.

1. trackingSystem.js: createTrackingSystem(api) with
     onFrame(frame)         // when frame.frameId changes: detect -> state machine -> kalman update
     step(dt)               // every fixed step: kalman predict, controller, api.setGimbalRateCommand
     setMode('AUTO'|'MANUAL')   // MANUAL leaves the gimbal to the keyboard/buttons
     getStatus() -> { state, detection, estimate:{panDeg,tiltDeg,sigmaDeg}, gtPixel, errPx, timings }
   Timing: measure detect+track time per frame with performance.now() into a ring buffer.
   In AUTO mode, use the ROI (predicted pixel +/- roiMarginPx) when in TRACK, full frame otherwise.
2. overlay.js: draw on the PiP canvas AFTER the frame blit: bounding box around the selected blob
   (color by state), crosshair, small predicted-position marker, and a state label (SEARCH gray, ACQUIRE
   amber, TRACK green, LOST red, REACQUIRE orange) plus sigma circle. Keep all drawing under 1 ms.
   Scale detector pixel coords to the PiP size (320x240 from 640x480).
3. Manual arrow-key input while AUTO is on: switch to MANUAL automatically and show it.
4. Add a dev hook window.__sky.tracking = trackingSystem.

ACCEPTANCE (1x speed, AUTO mode, from load):
- Starts in SEARCH (Earth blocks first ~6 s), then raster scan finds S-2, goes ACQUIRE -> TRACK.
- Holds TRACK for the full ~50 s visible window with the beacon near the crosshair.
- At ~57 s the beacon is hidden: LOST -> (coast) -> REACQUIRE spiral -> ACQUIRE -> TRACK after ~69 s,
  every cycle, for at least 3 cycles.
- Report the fraction of visible time in TRACK over 3 cycles (using __sky ground truth) and the
  median detect+track ms. 60 FPS, no console errors.
- If lock is lost outside occlusion, do NOT retune blindly: report gimbal error traces and stop.
Commit message: "2D: closed-loop tracking and overlay"
```

---

## Phase 3: Realism and robustness

### Prompt 3A: Disturbances

```text
[PASTE PREAMBLE]

TASK: Add a seeded disturbance layer with Off/Low/Med/High presets and live sliders.

FILES YOU MAY TOUCH: src/tracking/disturbances.js (new), src/tracking/prng.js (new),
src/tracking/beacon.js (add perturbation uniforms), src/tracking/virtualCamera.js (add
setPointingOffset), src/tracking/trackingSystem.js (insert the sensor stage before the detector),
src/tracking/config.js, index.html + a new src/tracking/disturbancePanel.js (small collapsible panel,
match existing panel styling), tests/disturbances.test.js.

1. prng.js: mulberry32 seeded generator plus gaussian(); every random draw in the project from now on
   goes through it. disturbances.setSeed(seed) resets all streams.
2. Effects, each with its own stream, applied where it physically belongs:
   - Atmospheric turbulence: beacon image wander (correlated Ornstein-Uhlenbeck, px rms, corner freq Hz)
     plus scintillation (multiplicative log-normal intensity). Implemented as beacon uniforms
     (pixel offset, intensity) so it happens BEFORE rendering the frame.
   - Platform vibration: angular jitter (deg rms, band-limited noise at vibrationHz) applied to the
     ACTUAL camera pointing via virtualCamera.setPointingOffset(panDeg, tiltDeg). Encoder readings in
     getGimbalState stay unaffected, so the controller does not see it. Ground truth is unaffected.
   - Sensor noise: gaussian read noise (sigma in 8-bit counts) plus a few hot pixels, applied to a COPY
     of frame.data; keep the raw frame for ground-truth debugging.
   - Blur: separable box/gaussian blur with radius in px on the frame copy.
   - Dropped frames: with probability p a feed frame is dropped (getFrame keeps the previous frameId, so
     the tracker sees no new frame) and a droppedFrames counter increments.
3. Presets: Off / Low / Med / High as objects in DISTURBANCE_PRESETS (choose sensible values; Med
   should visibly challenge but not break a tuned tracker; High should break it sometimes). Sliders
   for each parameter override the preset. Show the active seed in the panel.
4. Order inside trackingSystem: raw frame -> disturbance sensor stage -> detector. The PiP displays the
   post-disturbance frame (what the detector sees).
5. Tests: same seed -> identical sequences; different seed -> different; Off preset leaves a frame
   byte-identical; noise sigma measured on a flat frame matches the setting within 10%.

ACCEPTANCE: With Low the system keeps lock. With Med it keeps lock >= 80% of visible time (report the
number). With High it degrades visibly and recovers via REACQUIRE. Off is byte-identical to before.
Switching presets at runtime has no console errors. Report FPS impact.
Commit message: "3A: disturbance layer"
```

### Prompt 3B: Decoys and blink-based identification

```text
[PASTE PREAMBLE]

TASK: Add decoys and identify the true beacon by its blink code, with multi-candidate tracking.

FILES YOU MAY TOUCH: src/tracking/decoys.js (new), src/tracking/beaconId.js (new),
src/tracking/candidateTracker.js (new), src/tracking/beacon.js (blink code support),
src/tracking/stateMachine.js and trackingSystem.js (feed the identified candidate only),
src/tracking/config.js, tests/beaconId.test.js, tests/candidateTracker.test.js.

1. Beacon coding: replace the simple blink with a repeating on/off code (default 8-bit code, bit period
   3 feed frames = 100 ms, so 10 bits/s and safe for a 30 Hz feed). config: BEACON_CODE = { bits:
   '10110010', bitPeriodSec: 0.1 }. Keep the steady mode selectable.
2. decoys.js: DECOY_CONFIG list. Types: (a) static "star" point sources fixed in inertial space,
   (b) a steady-light decoy satellite on its own small orbit, (c) a glint that flashes randomly
   (Poisson) near S-2's projected position. All rendered on BEACON_LAYER, all similar brightness and
   size to the beacon, seeded via prng. Decoys have NO code (steady or random). Count and type
   selectable, Off by default.
3. candidateTracker.js: nearest-neighbor data association with a pixel gate (from Kalman prediction for the
   main track, growing gate for new candidates). Each candidate keeps a rolling intensity history of
   the last N frames (N = 2 * code length in frames).
4. beaconId.js: matched-filter correlation of each candidate's binary-thresholded intensity history
   against the known code (all cyclic shifts), returning score in [0,1]; a candidate is CONFIRMED
   when score >= idThreshold for idConfirmFrames. Only the confirmed candidate goes to the Kalman
   filter and controller. Until confirmed, ACQUIRE keeps the gimbal centered on the strongest
   unconfirmed candidate but does not enter TRACK.
5. Tests: correct code -> score ~1; steady decoy -> score low; random flasher -> low; correct code with
   20% frame drops still confirms within a bounded number of frames; two candidates, confirmed one
   wins.

ACCEPTANCE: with 3 decoys and Med disturbances, tracker locks the real beacon and never TRACKs a
decoy over 3 orbit cycles (report false-lock count = 0 and time-to-confirm). With decoys off the
behaviour matches 2D. 60 FPS.
Commit message: "3B: decoys and blink ID"
```

**Optional 3B+ (only if time allows): small learned classifier.** Ask the agent for `scripts/trainClassifier.mjs` (logistic regression or a 2-layer MLP on features: area, peak, blink score, motion consistency), trained on synthetic candidate data from the seeded simulator, exported to `src/tracking/classifierWeights.json`, with JS-only inference in `src/tracking/classifier.js` used as a tie-breaker. Compare with and without it in the benchmark before deciding to keep it.

### Prompt 3C: Metrics module, HUD and charts

```text
[PASTE PREAMBLE]

TASK: Measure performance against ground truth and show it live.

FILES YOU MAY TOUCH: src/tracking/metrics.js (new), src/tracking/hud.js (new),
src/tracking/charts.js (new), index.html (one HUD/chart panel, matching styles),
src/tracking/trackingSystem.js (emit samples), src/tracking/config.js, tests/metrics.test.js.

1. metrics.js: createMetrics() consumes per-feed-frame samples
   { simTime, state, groundTruth:{pixelX,pixelY,inFrustum, losClear}, estimatePx, detectionPx,
     procMs, fps, confirmedId } and state-change events. Produces (precise definitions, document
   them in JSDoc AND in docs/METRICS.md):
   - observable(t): line of sight clear AND target inside the gimbal's reachable range.
   - Acquisition time: sim seconds from the first observable instant to the first TRACK. Also report
     time from scenario start.
   - Reacquisition time: per occlusion, from observable again to TRACK again (list + mean + max).
   - Pointing error (px and mrad): distance from image centre to the ground-truth pixel while observable
     and TRACK. Tracking error: distance from the estimate to the ground-truth pixel. Report mean, RMS,
     max, p95 for both. mrad = px * (fovDeg in rad / image height px).
   - Lock retention rate: time in TRACK with pointing error < lockRadiusPx (config, 30) divided by
     observable time.
   - False locks: TRACK spans whose estimate is farther than falseLockPx from ground truth for > 1 s.
   - Processing time: mean, p95, max of detect+track ms per frame. FPS: mean and min of render FPS.
   - Dropped feed frames count.
   reset(), getSummary(), getTimeSeries() (decimated), exportRows().
2. hud.js: compact live readout: state, lock time, current errors, retention so far, ms/frame, FPS.
3. charts.js: tiny canvas line charts, no libraries: pointing error (px) vs time, processing ms vs
   time, and a state-timeline strip colored by state. Last 60 s window, redraw at 5 Hz.
4. Tests: feed scripted samples and assert each metric on hand-computed values, including one
   occlusion with a known reacquisition time.

ACCEPTANCE: after 3 orbit cycles in AUTO the HUD numbers match expectations you can verify from the
state timeline (report them). Charts render without slowing the main view below 55 FPS.
Commit message: "3C: metrics, HUD, charts"
```

### Prompt 3D: Seeded scenarios and one-click benchmark

```text
[PASTE PREAMBLE]

TASK: Reproducible scenarios and a one-click benchmark that exports its log.

FILES YOU MAY TOUCH: src/tracking/scenarios.js (new), src/tracking/benchmark.js (new),
src/tracking/exporter.js (new), src/main.js (turbo-run hook and benchmark button wiring),
index.html (RUN BENCHMARK button and progress bar in the HUD panel), src/tracking/config.js,
docs/BENCHMARK_SCHEMA.md (new).

1. scenarios.js: SCENARIOS array of { id, name, seed, durationSimSec (default 190 = 3 cycles),
   disturbancePreset, decoys, simSpeed, slewPreset }. Include: S0 clean baseline, S1 Low, S2 Med, S3 High,
   S4 Med + 3 decoys, S5 occlusion at 4x speed, S6 PS-slew (30 deg/s) stress, S7 High + decoys.
   Run each with seeds [1, 2, 3].
2. benchmark.js: runBenchmark({scenarios, seeds, onProgress}) resets the world (sim clock, orbits at
   initial phase, tracker, metrics, PRNG seed), then runs in TURBO mode: repeatedly call the fixed-step
   loop for as many steps as fit in ~12 ms per animation frame, skipping the main-scene render except
   every Nth frame for the progress display. Feed frames are still rendered (the detector needs
   them). Collect summaries per (scenario, seed).
3. Determinism: running the same (scenario, seed) twice must produce identical summaries. Add a
   `runDeterminismCheck()` that does this for S2 and logs PASS/FAIL, and call it from the HUD via a
   small link.
4. exporter.js: export benchmark-<ISO timestamp>.json (full: config snapshot, git-less version
   string from package.json, per-run summaries, decimated time series) and .csv (one row per run;
   columns documented in docs/BENCHMARK_SCHEMA.md). Use Blob download now; leave a single
   `saveFile(name, blob)` seam that Electron will override later.
5. Aggregate table at the end: per scenario, mean +/- std across seeds for the headline metrics.

ACCEPTANCE: one click runs all scenarios x 3 seeds without freezing the UI, then downloads JSON and CSV.
Determinism check passes. Report total wall-clock runtime and the aggregate table.
Commit message: "3D: scenarios and benchmark"
```

---

## Phase 4: Packaging, documents, demo

You didn't give a deadline. Tell me the date and I'll back-schedule this phase. Aim to finish Phase 3 with at least a week left.

### Prompt 4A: Electron packaging

Confirm your target OS first. This prompt assumes **Windows x64**.

```text
[PASTE PREAMBLE]

TASK: Package the app as a standalone Electron executable that works offline on a clean machine.

FILES YOU MAY TOUCH: electron/main.cjs (new), electron/preload.cjs (new), package.json (scripts, main,
electron and electron-builder devDependencies, "build" config), vite.config.js, src/loadAssets.js
(asset URLs and Draco removal only), src/tracking/exporter.js (saveFile override), index.html (CSP
meta tag only).

1. vite.config.js: base './'. src/loadAssets.js: build asset URLs from import.meta.env.BASE_URL
   instead of absolute '/assets/...'. Remove the DRACOLoader and its gstatic CDN URL entirely (verified:
   none of the three GLBs use Draco). Confirm no other network requests remain (grep for http).
2. electron/main.cjs: BrowserWindow 1600x900, contextIsolation on, nodeIntegration off, load
   dist/index.html via file://, menu bar hidden, window title "Sky Lock". Offer a GPU fallback:
   if env SKYLOCK_SOFTWARE_GL=1 call app.disableHardwareAcceleration(). preload.cjs exposes only
   window.skylock.saveFile(name, dataUint8Array) via IPC using dialog.showSaveDialog and fs.writeFile.
   The renderer's saveFile seam uses it when present and falls back to a Blob download otherwise.
3. package.json scripts: "electron:dev" (vite + electron), "dist" (vite build + electron-builder).
   electron-builder: Windows NSIS installer plus a portable exe, appId com.skylock.app, include only
   dist/ and electron/.
4. Add a CSP meta tag: default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline';
   script-src 'self'; connect-src 'self'.
5. docs/CLEAN_MACHINE_TEST.md: a checklist (fresh Windows VM or Windows Sandbox, no Node, no internet):
   install/run, Earth textures load, tracking reaches TRACK, benchmark runs, JSON/CSV saved.

ACCEPTANCE: `npm run dist` produces the installer and portable exe. Launch the portable exe with the
network disabled: no blank screen, Earth and satellites render, tracking works, benchmark export opens
the save dialog. Report exe size and first-frame time.
Commit message: "4A: electron packaging"
```

### Prompt 4B: Polish and code hygiene

```text
[PASTE PREAMBLE]

TASK: A UI polish and cleanliness pass. No behavior changes, no file moves, no renames.

FILES YOU MAY TOUCH: index.html (CSS and layout only), src/ui.js and src/tracking/*.js (comments,
dead code, logging only), src/loadAssets.js (set DEBUG_MODE false), README.md, docs/CONFIG.md (new).

1. Layout: at 1366x768 and 1920x1080 the PiP, HUD, charts, comms console and control panel must not
   overlap, and each must be collapsible. Consistent fonts, spacing, state colors (same as overlay).
2. Keyboard help overlay on `?` listing every shortcut.
3. Remove leftover debug code, commented-out blocks and TEMPORARY/TODO markers that are done.
   Silence verbose logs behind a single `DEBUG` flag in config.js. Keep meaningful startup logs.
4. JSDoc on every export and a short header comment on every module saying its role and its inputs/outputs.
   Zero ESLint warnings; run prettier over src/ only.
5. docs/CONFIG.md: a table of every config key (name, meaning, unit, default, PS reference if any).
6. README.md: rewrite for the real project (features, architecture diagram in ASCII, how to run/test/
   benchmark/package, module map).

ACCEPTANCE: `npm run lint` has zero warnings, `npm test` and `npm run build` pass, before/after
benchmark summaries (S2, seed 1) are identical, no console errors on load.
Commit message: "4B: polish and hygiene"
```

### Prompt 4C: Evidence and document drafts

Run the full benchmark first and keep the JSON. The technical report and user manual should be drafted from real numbers only.

```text
[PASTE PREAMBLE]

TASK: Produce the raw material and first drafts for the technical report and user manual.

FILES YOU MAY TOUCH: src/tracking/capture.js (new), src/main.js (one key binding, `P`),
scripts/benchmark-to-md.mjs (new), docs/report-draft.md (new), docs/user-manual-draft.md (new),
docs/figures/ (new, output only).

1. capture.js: on key `P`, save a PNG named skylock-<state>-<simTime>.png containing the main view and the
   PiP side by side (capture immediately after the render call so the buffer is valid). Uses
   exporter.saveFile.
2. scripts/benchmark-to-md.mjs <benchmark.json>: prints Markdown tables (per-scenario mean +/- std
   for: acquisition time, mean/max pointing error, lock retention, false locks, ms/frame, FPS) and a
   run-configuration table. Write to docs/figures/benchmark-tables.md.
3. docs/report-draft.md, target 10 to 15 pages (about 4,500 to 6,500 words plus figures). Sections and
   page budget: 1 Introduction and requirements (1), 2 System architecture with a block diagram (2),
   3 Sensing: camera model, beacon, rendering pipeline (1.5), 4 Detection (1.5), 5 Estimation and
   control with the Kalman and PID design and tuning (2), 6 State machine and search/reacquire strategy
   including the 12 s occlusion analysis (1.5), 7 Robustness: disturbances, decoys and blink coding (1.5),
   8 Results from the benchmark (2), 9 Limitations and future work (0.5), 10 Conclusion (0.5).
   RULES: every number must come from docs/figures/benchmark-tables.md or the config; if a number is
   not available write [[NEED: ...]] instead of inventing one; mark screenshot spots as
   [[FIG: filename - caption]].
4. docs/user-manual-draft.md: install (installer and portable), first run, GUI tour panel by panel,
   controls and shortcuts, every user-adjustable parameter (from docs/CONFIG.md), how to run the
   benchmark and read the output, troubleshooting (blank screen -> SKYLOCK_SOFTWARE_GL=1).

ACCEPTANCE: `P` writes a correct PNG; the script runs on a real benchmark JSON; the drafts contain no
invented numbers (grep for [[NEED: markers and list them in your report).
Commit message: "4C: evidence and doc drafts"
```

When the drafts are done, upload them with the screenshots and I can turn them into the final **.docx or PDF** report and manual (formatting, figures, captions, page count check).

### Prompt 4D: Demo mode and submission package

```text
[PASTE PREAMBLE]

TASK: A scripted demo mode for the 3 to 5 minute video, plus a one-command submission zip.

FILES YOU MAY TOUCH: src/tracking/demoMode.js (new), src/main.js (wiring and one key binding, `D`),
docs/demo-script.md (new), scripts/package-submission.mjs (new), package.json (script only).

1. demoMode.js: a seeded, choreographed sequence that runs at 1x and needs no interaction:
   0:00 title card overlay; 0:15 clean lock (disturbances Off); ~1:05 first occlusion and recovery, with
   an on-screen caption "Earth occlusion: LOST -> REACQUIRE"; 2:00 switch to Med disturbances with
   caption; 2:40 add 3 decoys with caption "Blink-code ID rejects decoys"; 3:30 show benchmark
   summary overlay from the latest benchmark JSON (or the built-in aggregate); 4:00 end card. All
   captions are DOM overlays, timed by sim time. Key `D` starts/stops.
2. docs/demo-script.md: storyboard table (time, screen content, narration text, what to click) matching
   the sequence above, plus recording settings (1080p, 30 fps) and a retake checklist.
3. scripts/package-submission.mjs: builds a folder and zip skylock-submission-<date>.zip containing:
   source (no node_modules, dist, or .git), the installer and portable exe from release/, docs/ (PDF
   and DOCX if present), the demo video placeholder file name, benchmark JSON/CSV, and a top-level
   README.txt with run instructions. Print a manifest with file sizes and SHA-256 of the executables.

ACCEPTANCE: `D` plays the full sequence without touching the keyboard; the packaging script produces
the zip with the manifest; unzip it in a temp folder and confirm the tree is complete.
Commit message: "4D: demo mode and submission package"
```

---

## 5. Final checklist (tick before submission)

- [ ] Benchmark JSON/CSV from the **final** build, saved in `docs/`
- [ ] Report has 10 to 15 pages with real numbers and screenshots, no `[[NEED` left
- [ ] Manual covers install, operation, parameters, GUI
- [ ] Demo video is 3 to 5 minutes
- [ ] Installer tested on a clean, offline machine
- [ ] Submission zip unzipped and spot-checked
- [ ] Buffer of at least one full day before the deadline

## 6. Decisions I made that you should confirm

1. **Hide S-2's body in the feed** (point-source beacon), with a flag to bring it back as clutter.
2. **Default slew of 45°/s** because the geometry needs \~36°/s; keep 30°/s as the PS stress preset unless the PS mandates 30 (then Prompt 0 handles it).
3. **Pan wraps** across ±180° (shortest path) when the pan limit is 180° or more.
4. **Detection by chroma** (magenta beacon) plus size filtering; luma mode stays as a fallback.
5. **Windows x64** as the Electron target.