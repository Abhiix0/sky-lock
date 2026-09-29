# Sky Lock - Operator's Manual & User Guide

**Document Version:** 1.0.0  
**Target Platform:** Windows 10/11 x64 (Standalone Offline Desktop & Modern Web)  
**Applicable Build:** Sky Lock v1.0.0 (Production Release)  

---

## 1. System Overview

**Sky Lock** is an autonomous electro-optical inter-satellite tracking and acquisition simulator engineered for inter-satellite laser communication links (ISL). Operating across Low Earth Orbit (LEO) orbital regimes, Sky Lock simulates the dynamic closed-loop pointing, acquisition, and tracking (PAT) system of an observer satellite (S-1) tracking a target beacon satellite (S-2).

The application features:
- **Two-satellite orbital simulation** with real-time 3D Earth rendering, ephemeris integration, and line-of-sight (LOS) occlusion checks.
- **Physical 2-axis gimbal actuator** with realistic torque, slew rate, and acceleration constraints.
- **640×480 @ 30 Hz optical tracking sensor** with custom blob detection, intensity centroiding, and circularity filtering.
- **Extended Kalman Filter (EKF)** state estimator supporting up to 12 seconds of coasting across planetary occlusions.
- **2-axis PID rate controller** with angular velocity feed-forward.
- **Manchester-coded optical beacon identification** with normalized cross-correlation matched filtering to reject bright decoys and optical clutter.
- **Multi-scenario benchmark suite** evaluating lock retention, RMS pointing error, and latency across 8 standardized stress scenarios.

---

## 2. Installation and Deployment

Sky Lock is distributed as a completely self-contained, offline-first application that requires zero external network connectivity or cloud runtime dependencies.

### 2.1 Distribution Formats

| Distribution Type | Executable Name | Target Architecture | Installation Footprint | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Portable Standalone** | `Sky Lock 1.0.0.exe` | Windows x64 | ~111 MB | Single-file zero-install executable. Run from any local or USB drive. |
| **Windows NSIS Installer** | `Sky Lock Setup 1.0.0.exe` | Windows x64 | ~112 MB | Standard Windows wizard installer with Desktop shortcut and uninstaller. |
| **Web Dev Server** | Source Tree | Any (Node.js 18+) | ~400 MB (`node_modules`) | Launched via `npm run dev` running Vite on port 3000. |

### 2.2 System Requirements

- **Operating System**: Windows 10 64-bit or Windows 11 64-bit.
- **Processor**: Intel Core i5 / AMD Ryzen 5 or better (Dual-core minimum, Quad-core recommended).
- **Memory**: 4 GB RAM minimum (8 GB recommended).
- **Graphics**: Hardware WebGL 2.0 / OpenGL 3.3 compatible GPU (Intel Iris Xe, NVIDIA GeForce, or AMD Radeon).
- **Storage**: 250 MB free disk space.
- **Network**: **None**. Fully functional air-gapped without internet access.

### 2.3 Installation Steps

#### Option A: Portable Standalone Executable
1. Download or copy `Sky Lock 1.0.0.exe` to your preferred directory (e.g., `C:\SkyLock\` or a portable flash drive).
2. Double-click `Sky Lock 1.0.0.exe`.
3. The application will initialize the Chromium sandbox, extract internal WebGL assets, and present the main simulation interface within ~1.5 seconds.

#### Option B: Windows Installer
1. Double-click `Sky Lock Setup 1.0.0.exe`.
2. Follow the on-screen prompts to select the installation directory (default: `C:\Users\<User>\AppData\Local\Programs\sky-lock`).
3. Click **Install**.
4. Check **Launch Sky Lock** and click **Finish**. A desktop shortcut will be placed on your desktop.

---

## 3. First Run and Startup

Upon launching Sky Lock:
1. The 1600×900 primary application window appears with a sleek dark sci-fi aerospace aesthetic.
2. The 3D scene automatically loads the textured Earth model and initializes the baseline S-1 and S-2 orbital trajectories.
3. The tracking state machine starts in **SEARCH** mode, executing a raster search pattern until the optical beacon on S-2 is acquired.
4. Once acquired, the system transitions to **ACQUISITION**, verifies target optical identity via matched filtering, and locks on in **TRACKING** mode.

---

## 4. User Interface Tour: Panel by Panel

The Sky Lock graphical user interface is structured around 5 key telemetry and control panels positioned around the perimeter of the primary 3D viewport. Each panel is collapsible to ensure an unobstructed view across both 1366×768 (laptop) and 1920×1080 (workstation) display resolutions.

```
+-------------------------------------------------------------------------------+
| TOP BAR: Simulation Clock | Mode Badge | Time Acceleration | FPS Counter      |
+----------------------+---------------------------------+----------------------+
| LEFT PANELS:         | CENTER:                         | RIGHT PANELS:        |
|                      |                                 |                      |
| [1] Gimbal Cam (PiP) | Primary 3D Orbital Viewport     | [3] Control Panel    |
|   - 640x480 Feed     |   - Earth & Satellites (S-1/S-2)|   - Manual Orbits    |
|   - Centroid Crosshair|  - Inter-Satellite Link Beam   |   - Presets / Slew   |
|   - Gimbal Telemetry |   - Camera Orbit Controls       |   - Decoy Injection  |
|                      |                                 |                      |
| [2] Comms Console    |                                 | [4] Disturbance Panel|
|   - Range / Az / El  |                                 |   - Noise Presets    |
|   - Link Margin (dB) |                                 |   - Jitter / Vibration|
|   - Doppler / LOS    |                                 |                      |
|                      |                                 | [5] Metrics & Charts |
|                      |                                 |   - Real-time Error  |
|                      |                                 |   - Lock Retention   |
|                      |                                 |   - Benchmark HUD    |
+----------------------+---------------------------------+----------------------+
| BOTTOM BAR: Keyboard Shortcut Help (? key) | System State Bar                 |
+-------------------------------------------------------------------------------+
```

### Panel 1: Gimbal Optical Feed (Picture-in-Picture)
Located in the upper-left corner:
- **Optical Canvas (`#gimbal-cam-canvas`)**: Displays the 20° FOV sensor feed from the S-1 gimbal camera at 30 Hz.
- **Dynamic Crosshair Overlay**:
  - **Cyan Center Crosshair**: Optical boresight axis $(0, 0)$.
  - **Dynamic Reticle**: Shows the detected beacon position or Kalman-predicted position.
  - **Color-Coded State Border**:
    - Cyan: `SEARCH`
    - Yellow: `ACQUISITION`
    - Green: `TRACKING`
    - Orange: `COASTING`
    - Red: `LOST`
- **Telemetry Readout**: Live azimuth/elevation gimbal angles and measured centroid offset in pixels and milliradians.
- **Collapse Button (`#gimbal-collapse-btn`)**: Minimizes the panel during wide-angle constellation reviews.

### Panel 2: Telemetry & Communications Console
Located in the lower-left corner:
- **Inter-Satellite Range**: Instantaneous separation between S-1 and S-2 in kilometers.
- **Link Status**: Visual LOS indicator (`CLEAR` vs `EARTH OCCLUDED`).
- **Optical Link Margin**: Computed link budget in decibels (dB), accounting for free-space path loss and pointing jitter.
- **Doppler Shift**: Relative radial velocity between satellites.
- **Collapse Button (`#comms-collapse-btn`)**: Folds the console.

### Panel 3: Constellation & Actuator Control Panel
Located in the upper-right corner:
- **Satellite Selector**: Toggles between automatic Keplerian orbits and manual inclination/altitude tweaking.
- **Gimbal Mode**: Toggles between `AUTO` closed-loop tracking and `MANUAL` rate control.
- **Actuator Slew Presets**: Select between `stress` (30°/s), `baseline` (45°/s), and `fast` (60°/s).
- **Collapse Button (`#control-collapse-btn`)**: Folds control panel.

### Panel 4: Environmental Disturbance Panel
Located in the middle-right:
- **Disturbance Presets**:
  - `OFF`: Ideal orbital kinematics without noise.
  - `LOW`: Mild atmospheric drag, thermal drift, and sensor readout noise ($0.2\text{ px}$ $\sigma$).
  - `MED`: Realistic orbital perturbations, reaction wheel harmonic jitter ($100\text{ Hz}$ / $250\text{ Hz}$), sensor noise ($0.8\text{ px}$ $\sigma$).
  - `HIGH`: Severe high-frequency structural flexure, solar radiation pressure, optical noise ($2.5\text{ px}$ $\sigma$).
- **Decoys Injection Switch**: Spawns 3 competing optical emitters with pseudo-random drift and blink rates to evaluate matched-filter discrimination.
- **Collapse Button (`#disturbance-collapse-btn`)**: Folds disturbance panel.

### Panel 5: Real-Time Performance Metrics & Charts
Located in the lower-right corner:
- **Pointing Error Strip-Chart**: Canvas-based real-time oscillograph showing instantaneous pointing error (pixels / mrad) against the $0.5\text{ mrad}$ requirement envelope.
- **Lock Retention Rate**: Running percentage of observable mission time maintained in `TRACKING` lock.
- **Mean & 95th Percentile Error**: Statistical telemetry summary.
- **Run Benchmark Button (`#btn-run-benchmark`)**: One-click execution of the full 24-scenario test suite.
- **Collapse Button (`#metrics-collapse-btn`)**: Folds metrics panel.

---

## 5. Controls and Keyboard Shortcuts

Sky Lock offers comprehensive hotkey controls for rapid operator intervention and headless automation. Press **`?`** or **`Shift + /`** at any time to display the in-app cheat sheet modal.

| Key / Shortcut | Function | Context |
| :--- | :--- | :--- |
| **`Space`** | Pause / Resume simulation clock | Global |
| **`1`** | Set simulation speed to 1x (Real-time) | Global |
| **`2`** | Set simulation speed to 2x | Global |
| **`5`** | Set simulation speed to 5x | Global |
| **`0`** | Set simulation speed to 10x | Global |
| **`P`** | **Capture Frame**: Exports side-by-side high-res PNG (`skylock-<state>-<time>.png`) | Global |
| **`D`** | **Demo Mode**: Toggles automated choreographed 4-minute presentation | Global |
| **`?`** or **`Shift+/`** | Open Keyboard Help Modal | Global |
| **`Arrow Left / Right`** | Manual Gimbal Pan (Azimuth rate nudge) | Switches to MANUAL mode |
| **`Arrow Up / Down`** | Manual Gimbal Tilt (Elevation rate nudge) | Switches to MANUAL mode |
| **`Shift + Arrows`** | Fast Manual Gimbal Slew (3x rate boost) | MANUAL mode |
| **`Left Mouse Drag`** | Orbit 3D viewport camera around Earth | Viewport |
| **`Right Mouse Drag`**| Pan 3D viewport camera | Viewport |
| **`Mouse Scroll`** | Zoom 3D viewport in / out | Viewport |

---

## 6. User-Adjustable Parameters Reference

All operational parameters are exposed in `docs/CONFIG.md` and can be adjusted dynamically in the GUI or tuned via `src/tracking/config.js`.

### 6.1 Optical Sensor & Gimbal Parameters
- **`CAMERA_CONFIG.fovDeg`** (`20.0°`): Camera field of view. Lowering this increases angular magnification but narrows the acquisition basket.
- **`CAMERA_CONFIG.slewRateDegPerSec`** (`45.0°/s`): Maximum servo angular rate for both azimuth and elevation axes.
- **`CAMERA_CONFIG.slewAccelDegPerSec2`** (`120.0°/s²`): Maximum actuator angular acceleration limit.

### 6.2 Detector Tuning
- **`DETECTOR_CONFIG.mode`** (`'chroma'`): Segmentation algorithm. `'chroma'` isolates the saturated 850 nm beacon signature, effectively rejecting high-albedo Earth background reflections.
- **`DETECTOR_CONFIG.threshold`** (`128` LSB): Pixel discrimination cutoff.
- **`DETECTOR_CONFIG.minCircularity`** (`0.35`): Shape compactness cutoff ($4\pi A / P^2$) ensuring elongated solar reflections are rejected.

### 6.3 Kalman Estimator
- **`KALMAN_CONFIG.sigmaProcess`** (`0.8°/s²`): Line-of-sight acceleration disturbance covariance $q_{\text{pos}}$.
- **`KALMAN_CONFIG.sigmaMeasure`** (`0.05°`): Sensor pixel measurement standard deviation $R$.
- **`KALMAN_CONFIG.maxCoastTimeSec`** (`12.0 s`): Coasting deadline. During orbital occultations behind Earth, the Kalman filter coasts forward on orbital velocity estimates for up to 12 seconds before declaring target loss and entering raster search.

### 6.4 Closed-Loop Controller
- **`CONTROLLER_CONFIG.kp`** (`1.8`): Proportional error gain.
- **`CONTROLLER_CONFIG.ki`** (`0.15`): Integral gain for eliminating steady-state gimbal bias.
- **`CONTROLLER_CONFIG.kd`** (`0.35`): Derivative damping gain to prevent overshoot during rapid slews.
- **`CONTROLLER_CONFIG.feedForwardEnabled`** (`true`): Injects Kalman-estimated angular velocity directly into gimbal rate commands to eliminate tracking lag.

---

## 7. Running the Benchmark Suite

The built-in benchmark runner evaluates the tracking pipeline across 8 standardized scenarios with 3 randomized PRNG seeds each (24 total scenario runs).

### 7.1 Scenario Definitions
- **S0 (Clean Baseline)**: Disturbance OFF, Decoys OFF, 45°/s slew. Tests ideal orbital geometry and sensor noise floor.
- **S1 (Low Perturbation)**: Disturbance LOW, Decoys OFF, 45°/s slew. Tests mild solar pressure and thermal noise.
- **S2 (Medium Perturbation)**: Disturbance MED, Decoys OFF, 45°/s slew. Realistic operational environment with reaction wheel jitter.
- **S3 (High Perturbation)**: Disturbance HIGH, Decoys OFF, 45°/s slew. Extreme spacecraft vibration.
- **S4 (Stress Slew Limit)**: Disturbance MED, Decoys OFF, 30°/s slew. Evaluates tracking performance under actuator rate saturation.
- **S5 (Decoy Clutter Discrimination)**: Disturbance OFF, 3 Decoys ON, 45°/s slew. Verifies matched-filter rejection of decoys.
- **S6 (Combined Clutter & Jitter)**: Disturbance MED, 3 Decoys ON, 45°/s slew. Tests joint disturbance rejection and decoy discrimination.
- **S7 (Worst-Case Environment)**: Disturbance HIGH, 3 Decoys ON, 30°/s slew. Stress-test of entire PAT architecture.

### 7.2 Executing the Benchmark
1. In the **Metrics & Charts** panel, click **RUN BENCHMARK (8 SCENARIOS × 3 SEEDS)**.
2. The benchmark will run in accelerated simulation time slices without blocking the UI thread.
3. Progress is displayed in real-time on the progress bar.
4. Upon completion:
   - A comprehensive JSON file (`benchmark-<timestamp>.json`) is generated.
   - A standardized CSV file (`benchmark-<timestamp>.csv`) is saved.
   - In Electron, the files are written directly to your chosen folder. In a standard browser, downloads will trigger automatically.

### 7.3 Converting Benchmark JSON to Formatted Markdown
To generate presentation-ready Markdown tables for reports:
```bash
node scripts/benchmark-to-md.mjs docs/figures/benchmark.json
```
The output tables will be written directly to `docs/figures/benchmark-tables.md`.

---

## 8. Troubleshooting & FAQ

### Issue 1: Blank Screen or Black Canvas on Launch
**Symptom**: The window opens, but the 3D viewport remains black or displays WebGL context creation failure.  
**Root Cause**: Outdated graphics drivers or virtualization environments lacking hardware OpenGL 3.3 support.  
**Resolution**:
Launch Sky Lock with software OpenGL fallback enabled:
```powershell
$env:SKYLOCK_SOFTWARE_GL = "1"
.\release\"Sky Lock 1.0.0.exe"
```
Or set the Windows environment variable `SKYLOCK_SOFTWARE_GL=1` under System Properties -> Environment Variables.

### Issue 2: Tracking Reticle Jumps to Decoys
**Symptom**: During Decoy scenarios (S5–S7), the reticle momentarily tracks a non-target emitter.  
**Resolution**:
Verify that **Beacon Identification Mode** is set to `'code'` and matched filtering is enabled. In `'code'` mode, unmodulated decoys are rejected after the 8-bit correlation window (0.8 seconds).

### Issue 3: Frame Drops or Sluggish Rendering
**Symptom**: FPS drops below 30 FPS.  
**Resolution**:
1. Collapse unused UI panels to reduce DOM repaint load.
2. Ensure your monitor is connected to a dedicated GPU rather than an unaccelerated auxiliary display adapter.
3. Reduce simulation speed to 1x (`Key 1`).

---

*Sky Lock Autonomous Satellite Tracking System — Operator Manual v1.0.0*
