# SkyLock GUI Documentation

**Version:** 1.0  
**Target System:** SkyLock Optical Tracking System  
**GUI Framework:** PySide6 (Qt6)

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Threading Model](#threading-model)
3. [Configuration Management](#configuration-management)
4. [Widget-to-Config Mapping](#widget-to-config-mapping)
5. [Keyboard Shortcuts](#keyboard-shortcuts)
6. [MP4 Video Usage](#mp4-video-usage)
7. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The SkyLock GUI is built using **PySide6** (Qt6) and follows a clean separation between UI and core logic:

```
┌─────────────────────────────────────────────────────────────┐
│                        Main Thread                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │  MainWindow  │───>│ ControlsPanel│───>│ ConfigEditor │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│         │                    │                    │         │
│         │ signals            │ config_changed     │         │
│         ▼                    ▼                    │         │
│  ┌──────────────┐    ┌──────────────┐            │         │
│  │ TelemetryPanel│    │ BenchmarkPanel│            │         │
│  └──────────────┘    └──────────────┘            │         │
│         ▲                                         │         │
│         │ frame_ready                             │         │
│         │                                         │         │
│  ┌──────────────────────────────────────────────┐│         │
│  │            SessionWorker                     ││         │
│  │  (runs in separate QThread)                  ││         │
│  │                                               ││         │
│  │  ┌────────────┐  step() ┌─────────────────┐ ││         │
│  │  │  Session   │◀────────│  Pacer          │ ││         │
│  │  └────────────┘  FrameView └──────────────┘ ││         │
│  │        │                                     ││         │
│  │        ▼                                     ││         │
│  │  ┌────────────┐                              ││         │
│  │  │ StepResult │──> FrameView DTO             ││         │
│  │  └────────────┘                              ││         │
│  └───────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

- **MainWindow**: Top-level window coordinating all panels and docks
- **ConfigEditor**: Single source of truth for configuration; emits signals on changes
- **SessionWorker**: Worker thread running the tracking session (Session + Pacer)
- **FrameView**: DTO carrying frame image, metrics, and state from worker to UI

---

## Threading Model

### Main Thread (Qt Event Loop)
- **Responsibilities:**
  - Handle all UI interactions (button clicks, config changes, etc.)
  - Receive `FrameView` objects from worker via Qt signals
  - Update display widgets (camera view, telemetry, charts)
  - Never blocks on I/O or computation

### Worker Thread
- **Responsibilities:**
  - Run `Session.step()` in a paced loop (20-60 FPS)
  - Emit `FrameView` objects back to main thread via signals
  - Handle session lifecycle (initialize, reset, close)
  - Managed by QThread with moveToThread() pattern

### Thread Safety
- **Configuration updates:** Config changes from UI are queued via signals/slots and applied atomically by worker
- **Back-pressure:** Camera view emits `frame_painted` signal; worker waits before sending next frame
- **Clean shutdown:** Worker thread is stopped with blocking QMetaObject.invokeMethod() call during window close

---

## Configuration Management

### Single Owner Pattern

```
ConfigEditor (main thread)
    ↓ (owns)
SkyLockConfig (immutable)
    ↓ (emits config_changed signal)
SessionWorker (worker thread)
    ↓ (rebuilds)
Session (new instance with updated config)
```

**Key Principles:**
1. **ConfigEditor owns the authoritative config**
2. **All UI widgets read from and write to ConfigEditor**
3. **Changes propagate via `config_changed` signal**
4. **Worker receives immutable snapshots**
5. **No widget caches config values**

### Config Update Flow

```python
# User changes a control
widget.valueChanged.emit(new_value)
    ↓
editor.override({"dotted.key": new_value})
    ↓
editor.config_changed.emit(new_config)  # immutable
    ↓
worker.apply_config(new_config)
    ↓
session = Session(new_config)  # rebuild
```

---

## Widget-to-Config Mapping

| UI Control | Config Key | Type | Range/Options |
|------------|-----------|------|---------------|
| **Camera** | | | |
| Width spinbox | `camera.width` | int | 320-1920 |
| Height spinbox | `camera.height` | int | 240-1080 |
| Horizontal FOV | `camera.fov_h_deg` | float | 1.0-10.0° |
| Vertical FOV | `camera.fov_v_deg` | float | 1.0-10.0° |
| Camera FPS | `camera.fps` | float | 1.0-120.0 |
| Allow <30 FPS checkbox | `camera.allow_below_spec_fps` | bool | - |
| **Gimbal** | | | |
| Slew rate slider | `gimbal.slew_rate_deg_s` | float | 0.1-10.0°/s |
| Pan limit | `gimbal.pan_limit_deg` | float | 1.0-180.0° |
| Tilt limit | `gimbal.tilt_limit_deg` | float | 1.0-90.0° |
| **Tracking** | | | |
| Scan rate | `tracking.search.scan_rate_deg_s` | float | 0.1-10.0°/s |
| Association gate | `tracking.association_gate_px` | float | 5.0-100.0 px |
| **Control** | | | |
| Control mode | `control.mode` | str | AUTO, MANUAL |
| Proportional gain (Kp) | `control.kp` | float | 0.0-1.0 |
| Integral gain (Ki) | `control.ki` | float | 0.0-1.0 |
| Derivative gain (Kd) | `control.kd` | float | 0.0-1.0 |
| Feed-forward (Kff) | `control.kff` | float | 0.0-1.0 |
| Deadband | `control.deadband_px` | float | 0.0-20.0 px |
| Latency frames | `control.latency_frames` | int | 0-10 |
| Manual rate | (UI only) | float | 0.1-10.0°/s |
| **Input** | | | |
| Source combo | `input.kind` | str | simulation, mp4 |
| MP4 path | `input.mp4_path` | str | file path |
| Loop video | `input.loop` | bool | - |
| **Target** | | | |
| Target count | `target.count` | int | 1-5 |
| Target size | `target.targets.N.size_px` | int | 5-20 px |
| Shape | `target.targets.N.shape` | str | square, disc, gaussian, cross |
| Brightness | `target.targets.N.brightness` | float | 100.0-255.0 |
| Initial | `target.targets.N.initial` | str | fixed, random |
| Initial position | `target.targets.N.initial_pos_deg` | tuple | (az, el) in degrees |
| Motion kind | `target.targets.N.motion.kind` | str | line, circle, figure8, random |
| **Disturbances** | | | |
| Gaussian noise | `disturbances.gaussian.enabled` | bool | - |
| Gaussian sigma | `disturbances.gaussian.sigma_levels` | float | 0.0-20.0 |
| Salt & pepper | `disturbances.salt_pepper.enabled` | bool | - |
| S&P density | `disturbances.salt_pepper.density` | float | 0.0-1.0 |
| Poisson noise | `disturbances.poisson.enabled` | bool | - |
| Poisson scale | `disturbances.poisson.photon_scale` | float | 1.0-10000.0 |
| Blur | `disturbances.blur.enabled` | bool | - |
| Blur sigma | `disturbances.blur.sigma_px` | float | 0.0-10.0 |
| Camera jitter | `disturbances.camera_jitter.enabled` | bool | - |
| Jitter max | `disturbances.camera_jitter.max_px_frame` | float | 0.0-20.0 |
| Jitter correlation | `disturbances.camera_jitter.correlation` | float | 0.0-1.0 |
| Platform motion | `disturbances.platform.enabled` | bool | - |
| Platform velocity | `disturbances.platform.velocity_px_frame` | float/tuple | ±20.0 |
| Atmosphere | `disturbances.atmosphere.enabled` | bool | - |
| Atmosphere mode | `disturbances.atmosphere.mode` | str | clear, haze, fog, rain, low_light |
| Atmosphere strength | `disturbances.atmosphere.strength` | float | 0.0-1.0 |
| **Other** | | | |
| Random seed | `seed` | int | 0-2³²-1 |

---

## Keyboard Shortcuts

| Shortcut | Action | Context |
|----------|--------|---------|
| **Ctrl+R** | Start tracking session | Global |
| **Ctrl+.** | Stop tracking session | Global |
| **Ctrl+Shift+R** | Reset session | Global |
| **Arrow Keys** | Manual gimbal control | MANUAL mode |
| **W** | Tilt up | MANUAL mode |
| **S** | Tilt down | MANUAL mode |
| **A** | Pan left | MANUAL mode |
| **D** | Pan right | MANUAL mode |
| **Ctrl+Q** | Quit application | Global (platform-dependent) |

### Manual Control Details

- **Mode:** Switch control mode to "MANUAL" in Controls panel
- **Rate:** Adjust "Manual Rate" spinbox to control speed (0.1-10.0°/s)
- **Keys:** Hold arrow keys or WASD for continuous motion
- **Multiple keys:** Can press Up+Right simultaneously for diagonal motion
- **Auto-repeat:** Ignored (only physical key press/release)
- **Focus:** Works even when spinboxes/combos have focus (exception: text fields being edited)
- **Window deactivate:** Rates reset to zero when window loses focus

---

## MP4 Video Usage

### Purpose
External video evaluation (Benchmark Performance-2) allows testing the tracking pipeline with evaluator-provided MP4 videos containing real noise and beacon motion.

### Setup
1. **Switch input source:** Select "mp4" from Input Source dropdown
2. **Browse MP4:** Click "Browse MP4..." and select video file
3. **Validation:** GUI automatically probes the video and shows:
   - ✅ Resolution, FPS, frame count (if valid)
   - ❌ Error message (if invalid/corrupt)
4. **Start disabled:** Start button disabled until valid MP4 selected

### Requirements
- **Format:** MP4 container (H.264/H.265 codec recommended)
- **Frame rate:** 30 FPS (others supported but may affect metrics)
- **Resolution:** Any (640×480 recommended for consistency)
- **Content:** Grayscale or color (converted to grayscale internally)

### Behavior
- **No ground truth:** MP4 videos have no ground-truth data
  - Acquisition time `from_first_observable` shows "—" (NOT_RUN)
  - Tracking error vs. ground truth shows "—"
  - Acquisition time `from_start` still measured
- **End-of-stream:** Status bar shows "Reached end-of-stream" when video completes
- **Loop option:** Check "Loop video" to repeat from beginning at EOS
- **FPS override:** If container FPS is unreadable, set FPS override manually

### Generating Test Videos
Use the provided script to generate deterministic test videos:
```bash
python scripts/gen_test_video.py --out test.mp4 --seconds 5.0 --seed 42 --fps 30.0
```

---

## Troubleshooting

### Common Issues

#### 1. Start Button Disabled
**Symptoms:** Cannot click Start button; button appears grayed out

**Causes:**
- Invalid configuration (check error label at top of Controls panel)
- MP4 input selected but no valid file chosen
- Session already running

**Solutions:**
- Check red error message in Controls panel
- If using MP4, browse and select a valid video file
- Verify probe status shows ✅ with file details
- If stuck, click Reset and try again

#### 2. "killTimer" or "QThread: Destroyed" Warnings
**Symptoms:** Console warnings about timers or threads when closing

**Causes:**
- Worker thread not cleanly shut down
- Timers not stopped before close

**Solutions:**
- Ensure latest version (bug fixed in G9)
- Stop any running session before closing
- Cancel any running benchmark before closing
- If persistent, report as bug with reproduction steps

#### 3. Configuration Changes Don't Take Effect
**Symptoms:** Changing a control doesn't affect the running session

**Causes:**
- Some config changes require session restart
- Validation error preventing update

**Solutions:**
- Check for red error message after changing value
- Stop and restart session to apply changes
- Reset session if values appear stuck

#### 4. MP4 Video Not Playing
**Symptoms:** Start button disabled after selecting MP4

**Causes:**
- Corrupt or unsupported MP4 file
- Missing codec support
- File path contains special characters

**Solutions:**
- Check probe status for error message
- Verify file plays in VLC or other media player
- Try re-encoding with H.264: `ffmpeg -i input.mp4 -c:v libx264 -cps 23 output.mp4`
- Avoid file paths with non-ASCII characters

#### 5. Low FPS / Stuttering
**Symptoms:** Wall FPS significantly below camera FPS

**Causes:**
- System overloaded (CPU/GPU)
- Debug mode enabled (slower)
- High resolution + disturbances
- Weak hardware

**Solutions:**
- Lower camera FPS (30 Hz instead of 60 Hz)
- Reduce resolution (640×480 instead of 1920×1080)
- Disable some disturbances
- Close other applications
- Use release build, not debug

#### 6. Ground Truth Overlay Not Visible
**Symptoms:** "Show ground truth" checked but no diamond marker

**Causes:**
- Using MP4 input (no ground truth available)
- Target outside current FOV
- Checkbox state not saved

**Solutions:**
- Ground truth only available for simulation input
- Check target is within gimbal pan/tilt limits
- Wait for target to enter FOV (random initial position)

#### 7. Acquisition Time Shows "—"
**Symptoms:** Acquisition time displays em dash instead of value

**Causes:**
- `from_first_observable` metric requires ground truth (NOT_RUN for MP4)
- Target never acquired (NOT_ACQUIRED)
- Never reached TRACK state

**Solutions:**
- For MP4: This is expected (no ground truth)
- For simulation: Check that target is visible and tracking active
- Verify TRACK state reached (telemetry badge shows "TRACK")

#### 8. Benchmark Fails with ConfigError
**Symptoms:** Benchmark run fails immediately with config error

**Causes:**
- Scenario requirements conflict with current config
- S16 (external MP4) without MP4 file selected

**Solutions:**
- Benchmark panel has its own config overrides
- For S16: Select MP4 file in benchmark panel before running
- Check scenario description for requirements
- Reset config to defaults and retry

### Performance Tuning

For best performance:
- **Resolution:** 640×480 (default)
- **Camera FPS:** 30 Hz (meets spec minimum)
- **Disturbances:** Enable selectively (each adds compute cost)
- **Control mode:** AUTO (MANUAL mode is for testing only)
- **Hardware:** Multicore CPU recommended; GPU not required

### Debug Mode

To enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will print detailed session, worker, and config information to console.

### Reporting Bugs

When reporting issues, please include:
1. **Version:** Output of `skylock --version`
2. **OS:** Windows/macOS/Linux version
3. **Python:** Output of `python --version`
4. **Qt:** Output of `python -c "from PySide6.QtCore import qVersion; print(qVersion())"`
5. **Config:** Export config as JSON (File → Save Config)
6. **Steps to reproduce:** Detailed steps to trigger the issue
7. **Screenshots:** If UI-related
8. **Logs:** Console output with debug logging enabled

---

## Known Limitations

1. **MP4 ground truth:** External MP4 videos have no ground-truth data; some metrics show "—"
2. **Real-time constraints:** At high FPS (60+) with many disturbances, wall FPS may lag camera FPS
3. **Window resize:** Camera view maintains 4:3 aspect ratio with letterboxing
4. **Benchmark concurrency:** Cannot run main session and benchmark simultaneously
5. **Config validation delay:** Some invalid configs only caught at session start, not at control change
6. **Manual mode persistence:** Manual rate and mode changes don't reset session but temporarily override AUTO

---

## Next Steps

For PyInstaller packaging and distribution:
- See `packaging/` directory for build scripts
- Windows: `build_windows.bat`
- macOS: `build_macos.sh`
- Linux: `build_linux.sh`

For advanced configuration and scripting:
- See `docs/CONFIG.md` for full config reference
- See `docs/BENCHMARK.md` for CLI benchmark usage
- See API documentation for programmatic control

---

**Document Version:** 1.0  
**Last Updated:** 2026-10-01  
**Maintainer:** SkyLock Development Team
