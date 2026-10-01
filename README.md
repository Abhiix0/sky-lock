# Sky Lock - Autonomous Free-Space Optical Beacon Tracking System

[![Tests](https://img.shields.io/badge/tests-43%20passed-brightgreen.svg)]()
[![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/platform-Web%20%7C%20Electron%20Windows%20x64-blue.svg)]()
[![Offline](https://img.shields.io/badge/network-100%25%20offline-success.svg)]()

**Sky Lock** is a high-fidelity space environment simulation and autonomous line-of-sight tracking system designed for inter-satellite Free-Space Optical Communications (FSOC). Mounted on an observer satellite (S-1), the 2-axis gimbal camera autonomously searches for, acquires, tracks, and reacquires an optical beacon emitted by a target satellite (S-2) in low Earth orbit.

The system features robust rejection of Earth albedo, sensor noise, beam wander, scintillation, structural jitter, and optical decoys using matched-filter periodic blink-code identification.

---

## Architecture Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                      SKY LOCK ARCHITECTURE                                        |
+---------------------------------------------------------------------------------------------------+
                                                                                                     
    +---------------------------+                     +----------------------------+                 
    |    Three.js 3D Engine     |                     |    Space Disturbances      |                 
    |   (Earth, S-1, S-2 bus)   |                     |   Turbulence, Wander,      |                 
    +-------------+-------------+                     |   Jitter, Scintillation    |                 
                  |                                   +-------------+--------------+                 
                  v                                                 |                                
    +-------------+-------------+                                   v                                
    |    Virtual Gimbal Cam     | -------------------> +------------+-------------+                  
    |  (Offscreen WebGL FBO)    |   Corrupted Frame    |      Blob Detector       |                  
    |     640x480 @ 30 Hz       |                      |  Chroma/Luma Segmentation|                  
    +---------------------------+                      +------------+-------------+                  
                                                                    | Centroids & Radiometry         
                                                                    v                                
    +---------------------------+                      +------------+-------------+                  
    |    Decoys & Clutter       |                      |    Candidate Tracker     |                  
    |  3x Modulated Emitters    |                      |  Spatial Gating & Assoc  |                  
    +---------------------------+                      +------------+-------------+                  
                                                                    | Tracked Intensities            
                                                                    v                                
    +---------------------------+                      +------------+-------------+                  
    |  Blink-Code Identification| <------------------- |   Matched-Filter Engine  |                  
    |  8-bit periodic Barker ID |   Confirmed Beacon   |   Pearson Correlation    |                  
    +-------------+-------------+                      +--------------------------+                  
                  |                                                                                  
                  v                                                                                  
    +-------------+-------------+                      +--------------------------+                  
    |  State Machine Controller |                      |     Kalman Filter        |                  
    | SEARCH -> ACQUIRE -> TRACK| <==================> | 4-State Const-Velocity   |                  
    |    LOST -> REACQUIRE      |                      | Continuous Line-of-Sight |                  
    +-------------+-------------+                      +------------+-------------+                  
                  |                                                 | State & Rate Estimates         
                  | Setpoint & State                                v                                
                  v                                    +------------+-------------+                  
    +-------------+-------------+                      |    PID Rate Controller   |                  
    |    Scan Generators        |                      |  Anti-Windup Integrator  |                  
    |  Raster / Expanding Spiral|                      |  Velocity Feed-Forward   |                  
    +---------------------------+                      +------------+-------------+                  
                                                                    | Commanded Slew Rates           
                                                                    v                                
                                                       +------------+-------------+                  
                                                       |     2-Axis Gimbal Rig    |                  
                                                       | Pan: [-180, 180] (Wrap)  |                  
                                                       | Tilt: [-60, +60] deg     |                  
                                                       +--------------------------+                  
```

---

## Key Features

1. **Autonomous 5-State Machine**:
   - `SEARCH`: Continuous raster sweep ($\pm 55^\circ$ elevation envelope, $360^\circ$ azimuth, $20\%$ row overlap).
   - `ACQUIRE`: Multi-frame candidate confirmation with spatial gating ($35\text{ px}$).
   - `TRACK`: Closed-loop Kalman filtering and feed-forward PID gimbal steering.
   - `LOST`: Up to $12.0\text{ s}$ coastal propagation on orbital kinematics during Earth occlusions.
   - `REACQUIRE`: Expanding Archimedean spiral search centered on predicted line-of-sight.

2. **Optical Beacon & Decoy Rejection**:
   - Sub-pixel Gaussian centroiding and chroma-difference background segmentation.
   - Matched-filter Pearson correlation evaluating candidate pulse trains against an 8-bit periodic signature (`10110010`).
   - Proven zero false locks against 3 competing optical decoys drifting at $0.2^\circ/\text{s}$.

3. **Space Environmental Disturbances**:
   - Beam wander modeled via 1st-order Gauss-Markov low-pass filtered wander.
   - Log-normal irradiance scintillation fluctuations.
   - Satellite bus reaction-wheel structural jitter ($10\text{ Hz}$).
   - Zero-mean Gaussian read noise, hot pixel defects, and frame drop modeling.

4. **Telemetry HUD & Real-Time Canvas Charts**:
   - Live metrics: Observable time, pointing error (RMS/mean/max in px and mrad), tracking error, latency percentiles, and FPS.
   - Strip-chart visualizers: Pointing error history, compute latency, and state timeline strip.

5. **Headless Turbo Benchmark Suite**:
   - Automated evaluation across 8 test scenarios (S0 through S7) across 3 reproducible PRNG seeds.
   - Headless execution at $>300\text{ FPS}$ with time-budgeted animation frame slicing.
   - Automatic export to CSV and JSON matching `docs/BENCHMARK_SCHEMA.md`.

6. **100% Offline Standalone Desktop Application**:
   - Packaged with Electron and `electron-builder` for Windows x64 (NSIS installer + portable executable).
   - Zero external CDN requests, local Draco-free assets, Content Security Policy enforcement, and software OpenGL fallback (`SKYLOCK_SOFTWARE_GL=1`).

---

## Module Map

```
sky-lock/
├── electron/
│   ├── main.cjs                # Electron main process (1600x900, IPC, GPU fallback)
│   └── preload.cjs             # Context isolation bridge (window.skylock.saveFile)
├── public/
│   └── assets/                 # Embedded GLB models (earth.glb, satellite.glb, satellite2.glb)
├── src/
│   ├── GLTFSpecGlossExtension.js # Specular-glossiness PBR shader extensions
│   ├── loadAssets.js           # GLTF asset loading and geometric normalization
│   ├── main.js                 # Primary simulation loop and state coordinator
│   ├── orbit.js                # Keplerian dual-satellite orbit propagation
│   ├── sceneSetup.js           # Three.js scene, lighting, stars, and orbit controls
│   ├── ui.js                   # Simulation controls and satellite management UI
│   └── tracking/
│       ├── beacon.js           # Optical beacon emitter shader and point rendering
│       ├── beaconId.js         # Matched-filter blink correlation and beacon confirmation
│       ├── benchmark.js        # Turbo headless benchmark runner and determinism check
│       ├── cameraPanel.js      # Picture-in-Picture feed canvas controller
│       ├── candidateTracker.js # Multi-target spatial gating and intensity history buffers
│       ├── capture.js          # Synchronous frame capture to PNG
│       ├── charts.js           # High-performance 2D canvas telemetry charts
│       ├── config.js           # Central constants, thresholds, and disturbance presets
│       ├── controller.js       # PID rate controller with anti-windup and feed-forward
│       ├── decoys.js           # Modulated decoy point sources and drift physics
│       ├── detector.js         # Sub-pixel blob detector and albedo filtering
│       ├── disturbancePanel.js # Sliders and disturbance preset UI controller
│       ├── disturbances.js     # Space turbulence, jitter, noise, and drop injection
│       ├── exporter.js         # Benchmark JSON/CSV formatter and file saving seam
│       ├── geometry.js         # Kinematics, coordinate transforms, and spherical projections
│       ├── hud.js              # Real-time telemetry HUD card grid
│       ├── kalman.js           # Constant-velocity 4-state line-of-sight Kalman filter
│       ├── linkLine.js         # Visual optical inter-satellite communication laser beam
│       ├── metrics.js          # Mathematical telemetry metrics accumulator
│       ├── overlay.js          # PiP crosshair, gating ring, and state badge HUD overlay
│       ├── scanPatterns.js     # Continuous raster search and Archimedean spiral algorithms
│       ├── scenarios.js        # Benchmark scenario definitions (S0 through S7)
│       ├── stateMachine.js     # Acquisition & tracking finite state machine
│       ├── trackingSystem.js   # Closed-loop tracking coordinator and pipeline orchestrator
│       └── virtualCamera.js    # Offscreen WebGL gimbal camera rig and render target
├── tests/                      # Comprehensive Vitest test suite (43 unit tests)
├── docs/
│   ├── BENCHMARK_SCHEMA.md     # CSV and JSON benchmark logging data specification
│   ├── CLEAN_MACHINE_TEST.md   # Offline clean machine verification checklist
│   ├── CONFIG.md               # Parameter table (name, meaning, unit, default, PS ref)
│   └── METRICS.md              # Mathematical definitions of tracking metrics
├── index.html                  # Responsive UI layout and HUD overlays
├── package.json                # Project dependencies, build scripts, and electron config
└── vite.config.js              # Vite bundler configuration (relative base './')
```

---

## Getting Started

### Prerequisites
- Python 3.10+ 
- pip (Python package manager)
- (Optional) Node.js 18+ and npm 9+ for legacy web version

### Installation

Install SkyLock with GUI and development dependencies:

```bash
# Clone the repository
git clone https://github.com/Abhiix0/sky-lock.git
cd sky-lock

# Install Python package with GUI support
pip install -e ".[gui,dev]"
```

For legacy web/Electron version:
```bash
# Install Node.js dependencies
npm install
```

### Running the GUI

Launch the graphical user interface:

```bash
# Start GUI with default configuration
skylock gui

# Start GUI with specific configuration file
skylock gui --config path/to/config.json
```

The GUI provides:
- **Live tracking visualization** with camera view and telemetry
- **Interactive controls** for all system parameters
- **Real-time metrics** and performance monitoring
- **Benchmark execution** with automated scenario testing
- **Configuration management** (load/save JSON configs)

See `docs/GUI.md` for complete GUI documentation.

### Running Benchmarks

Execute automated benchmark scenarios from the command line:

```bash
# Run specific scenario with seed
skylock bench --scenario S01_line_clean --seed 42

# Run multiple scenarios
skylock bench --scenario S01_line_clean S02_circle_clean --seeds 1,2,3

# Export results to JSON
skylock bench --scenario S01_line_clean --seed 42 --export results.json
```

See `docs/BENCHMARK.md` for benchmark documentation.

### Running Automated Tests
```bash
# Run the complete Vitest unit test suite (11 test files, 43 tests)
npm test
```

### Code Style & Linting
```bash
# Verify ESLint rules (0 errors, 0 warnings)
npm run lint

# Format codebase using Prettier
npm run format
```

### Production Build
```bash
# Compile web bundle to dist/
npm run build
```

---

## Desktop Packaging (Electron)

Sky Lock can be packaged as a standalone offline desktop application for Windows:

```bash
# Build Vite production bundle and package Windows installer + portable exe
npm run dist
```

Executables will be generated in `release/`:
- `release/Sky Lock Setup 1.0.0.exe` (NSIS Installer)
- `release/Sky Lock 1.0.0.exe` (Portable Executable, ~111 MB)

### Offline Execution & GPU Fallback
If running on a system with outdated or incompatible GPU hardware acceleration drivers:
```cmd
set SKYLOCK_SOFTWARE_GL=1
"Sky Lock 1.0.0.exe"
```

---

## Keyboard Controls

| Key | Action | Context |
| :--- | :--- | :--- |
| `?` or `Shift + /` | Toggle Keyboard Shortcuts Help Overlay | Global |
| `Space` | Pause / Resume Simulation Clock | Global |
| `1` / `2` / `4` | Set Simulation Speed (1x, 2x, 4x) | Global |
| `O` | Toggle Orbit Path Lines | Simulation |
| `L` | Toggle Optical Inter-Satellite Link | Simulation |
| `G` | Toggle Gimbal Camera PiP Feed | Tracking |
| `Arrow Keys` | Manual Gimbal Slew (Pan / Tilt) | Gimbal (Manual) |
| `Shift + Arrows` | Fast Manual Slew | Gimbal (Manual) |
| `C` | Center / Reset Bore-Sight (0°, 0°) | Gimbal |
| `B` | Run One-Click Benchmark Suite (8 Scenarios × 3 Seeds) | Benchmark |
| `P` | Capture High-Resolution Viewport PNG | Telemetry |
| `D` | Start / Stop Choreographed Demo Mode | Demo Mode |
| `Esc` | Close Modal Overlays | Global |

---

## License

MIT License. Designed and developed for the Sky Lock Free-Space Optical Communications Hackathon.
