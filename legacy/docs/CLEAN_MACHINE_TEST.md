# Sky Lock - Clean Machine Test Checklist

This checklist verifies that Sky Lock operates completely offline as a self-contained desktop application on a clean Windows machine without Node.js, developer tooling, or internet connectivity.

## Target Environment
- **Platform**: Clean Windows 10/11 x64 installation (or Windows Sandbox / fresh virtual machine)
- **Prerequisites**: No Node.js installed, no Git, no Python
- **Network State**: Fully offline (Airplane mode or network adapter disabled)

---

## Verification Checklist

### 1. Offline Transfer & Installation
- [ ] Transfer `Sky Lock Setup <version>.exe` (NSIS installer) and `Sky Lock <version>.exe` (portable exe) to the clean machine via USB drive or shared offline folder.
- [ ] Ensure machine network adapter is disconnected / disabled.
- [ ] Run the portable executable directly without administrator prompts.
  - [ ] App window opens titled `Sky Lock` at 1600x900 resolution.
  - [ ] No blank white/black screen.
  - [ ] Menu bar is hidden.
- [ ] Run the NSIS installer.
  - [ ] Installer wizard launches and completes installation cleanly.
  - [ ] Desktop and Start Menu shortcuts are created and launch the application.

### 2. Rendering & Asset Loading Verification
- [ ] Three.js 3D viewport initializes smoothly.
- [ ] 3D Earth renders with embedded day/night textures and specular highlights.
- [ ] Satellite 1 (chaser) and Satellite 2 (target) models load and render.
- [ ] Stars background and lighting (sun directional light and ambient fill) are visible.
- [ ] Orbit lines render smoothly around Earth.
- [ ] No missing texture warnings or missing asset error dialogs.

### 3. Tracking System & Hardware Acceleration
- [ ] Gimbal Camera Picture-in-Picture (PiP) feed renders at 640x480 (downsampled/displayed cleanly).
- [ ] Beacon detection identifies the optical beacon on Satellite 2.
- [ ] State Machine transitions through `INIT` -> `SEARCH` -> `ACQUIRE` -> `TRACK`.
- [ ] Crosshair overlay tracks the beacon accurately on the PiP feed.
- [ ] HUD displays real-time telemetry: State, Observable Time, Pointing Error, Latency, and Lock Retention.
- [ ] Real-time canvas charts display live pointing error and processing latency streams.

### 4. GPU Fallback Mode (Software Rendering)
- [ ] In Command Prompt (offline), launch portable exe with software GL override:
  ```cmd
  set SKYLOCK_SOFTWARE_GL=1
  "Sky Lock.exe"
  ```
- [ ] Verify application launches using SwiftShader/software OpenGL without crashes on systems with missing or outdated GPU drivers.

### 5. Disturbance & Decoy Rejection
- [ ] Toggle disturbance preset to `Med` (via HUD or Control Panel).
- [ ] PID/Kalman gimbal controller stabilizes line-of-sight pointing.
- [ ] Enable decoys. Verify candidate tracker and matched-filter blink ID reject decoys and maintain lock on the true beacon.

### 6. One-Click Benchmark Execution
- [ ] Click the **Run Benchmark** button on the control panel.
- [ ] Benchmark runs across all test scenarios in fast headless/turbo mode.
- [ ] Benchmark progress bar smoothly updates to 100%.
- [ ] Upon completion, native OS file save dialog opens automatically.
- [ ] Save both `benchmark-<timestamp>.json` and `benchmark-<timestamp>.csv` to local disk (e.g., Desktop or Documents).
- [ ] Verify both files contain valid data matching `docs/BENCHMARK_SCHEMA.md`.

---

## Pass Criteria Summary
| Metric | Acceptance Threshold | Verified |
| :--- | :--- | :---: |
| First-frame render latency | < 3.0 seconds from launch | [ ] |
| Standalone portable exe size | < 150 MB | [ ] |
| Network requests attempted | 0 (strictly offline) | [ ] |
| State reaching `TRACK` | Yes (within 2s in S0) | [ ] |
| Benchmark data exported | Valid JSON + CSV saved | [ ] |
