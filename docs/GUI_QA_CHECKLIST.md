# SkyLock GUI QA Checklist

**Version:** 1.0  
**Target:** Windows 11 (Primary), macOS/Linux (Secondary)  
**Test Duration:** ~30-40 minutes

---

## Prerequisites

- [ ] Windows 11 system with Python 3.10+
- [ ] SkyLock installed: `pip install -e ".[gui,dev]"`
- [ ] Test video generated: `python scripts/gen_test_video.py --out test.mp4 --seconds 5 --seed 42`
- [ ] Launch GUI: `skylock gui`

---

## 1. Window & Layout (5 min)

### Initial Display
- [ ] Window opens at reasonable size (~1280×800)
- [ ] Camera view shows "No Video Feed — Click 'Start' to begin"
- [ ] Left dock (Controls) is visible and scrollable
- [ ] Right dock (Telemetry) shows idle state (em dashes)
- [ ] Bottom tabs show "Benchmark" tab
- [ ] Menu bar has File, Run, View, Help menus
- [ ] Status bar shows: SEARCH | simulation | frame 0 | 0.0 fps

### Resize & Docks
- [ ] Resize window to 1100×700: all content visible, no clipping
- [ ] Resize window to 1920×1080: camera view dominates (~60% height)
- [ ] Close Controls dock (X button): dock disappears
- [ ] View → Controls: dock reappears
- [ ] Close Telemetry dock: dock disappears
- [ ] View → Telemetry: dock reappears
- [ ] Drag splitter between camera and tabs: both resize smoothly

### Theme
- [ ] Background is dark (#111827-like)
- [ ] Text is light and readable
- [ ] Groupbox titles are styled consistently
- [ ] Buttons have visible hover/press states
- [ ] Scrollbars are styled (dark with lighter handles)

---

## 2. Simulation Controls (5 min)

### Start/Stop/Reset
- [ ] Click Start (or Ctrl+R): button becomes disabled, Stop enabled
- [ ] Camera view shows live grayscale video
- [ ] Status bar updates: frame count increases, FPS shows ~30
- [ ] Click Stop (or Ctrl+.): video freezes, Start re-enabled
- [ ] Click Reset (or Ctrl+Shift+R): frame count resets to 0, camera clears

### Default Behavior (Slew 3.0 Valid - G-04)
- [ ] Set Gimbal slew rate to 3.0°/s: no config error
- [ ] Tracking scan rate follows (shows ≤ 3.0°/s)
- [ ] Start: session runs without error
- [ ] State Timeline shows colored segments (blue → amber → green)
- [ ] Telemetry → State badge cycles: SEARCH → ACQUIRE → TRACK
- [ ] Telemetry → LOCK changes from UNLOCKED to ENGAGED
- [ ] Acquisition time shows value < 2.0s (PS requirement)

---

## 3. Target Configuration (5 min)

### Target Motion (G-02)
- [ ] Target → Motion: select "Line"
- [ ] Start: target moves in straight line
- [ ] Stop, select "Circle": target moves in circular path
- [ ] Stop, select "Figure-8": target moves in figure-8 pattern ✓
- [ ] Stop, select "Random": target moves erratically

### Target Shapes (G-03)
- [ ] Target → Shape: select "Square": target appears as square
- [ ] Select "Disc": target appears as circle
- [ ] Select "Gaussian": target appears as soft blob
- [ ] Select "Cross": target appears as plus sign ✓
- [ ] All shapes track successfully

### Target Properties
- [ ] Size: change to 15 px: target appears larger
- [ ] Brightness: change to 200: target appears brighter
- [ ] Initial position: change to (1.0, 0.5): target starts at different location
- [ ] Multiple targets: set count to 2: two targets appear (if supported)

---

## 4. Disturbances (7 min - G-01/G-05/G-06)

**Check each disturbance individually:** Enable one, Start, run 5s, verify visible effect, Stop, disable, Reset.

- [ ] **Gaussian noise**: Image shows grainy texture ✓
- [ ] Gaussian sigma 10: Noise intensity increases
- [ ] **Salt & pepper**: White/black pixels scattered ✓
- [ ] S&P density 0.5: Many more speckles
- [ ] **Poisson noise**: Subtle photon noise ✓
- [ ] **Blur**: Image appears softer/less sharp ✓
- [ ] Blur sigma 3.0: Image very blurred
- [ ] **Camera jitter**: Image jitters/vibrates ✓
- [ ] Jitter max 10 px: Jitter amplitude increases
- [ ] **Platform motion**: Target appears to drift ✓
- [ ] Platform velocity [5,5]: Diagonal drift
- [ ] **Atmosphere - Clear**: No visible effect (baseline)
- [ ] **Atmosphere - Haze**: Image appears washed out ✓
- [ ] **Atmosphere - Fog**: Strong brightness reduction ✓
- [ ] **Atmosphere - Rain**: Streaks/droplets visible ✓
- [ ] **Atmosphere - Low light**: Image very dark ✓ (G-06)

**Critical:** No config errors when enabling any disturbance (G-01/G-05).

---

## 5. Control Modes (5 min - G-10/G-14)

### AUTO Mode
- [ ] Start in AUTO: tracker automatically centers target
- [ ] Target stays near boresight (center crosshair)
- [ ] Telemetry → Pointing shows small values (±few degrees)

### MANUAL Mode (G-10)
- [ ] Running session: change mode to MANUAL (no reset)
- [ ] Press Left arrow: telemetry → Pan decreases
- [ ] Press Right arrow: Pan increases
- [ ] Press Up arrow (or W): Tilt increases
- [ ] Press Down arrow (or S): Tilt decreases
- [ ] Press Left+Up simultaneously: Diagonal motion
- [ ] Manual rate 5.0°/s: Motion faster
- [ ] Focus on a spinbox: arrow keys still work (G-14)
- [ ] Switch back to AUTO: tracker resumes automatic control
- [ ] Session did NOT reset during mode changes (G-10)

---

## 6. Camera & Telemetry (5 min)

### Camera View
- [ ] Boresight crosshair at center (green/blue)
- [ ] Detections: yellow/amber circles around bright spots
- [ ] Estimate: cross/plus marker (blue when tracking, orange when predicting)
- [ ] Gate: dashed square around estimate (only in TRACK)
- [ ] Show ground truth: checkbox enables pink diamond marker
- [ ] Legend: checkbox shows "o detection  [ ] gate  + estimate  ◇ GT"
- [ ] Mouse hover: bottom-right shows pixel coordinates

### Telemetry Panel (G-16/G-18)
- [ ] State badge updates: SEARCH → ACQUIRE → TRACK → LOST → REACQUIRE
- [ ] Lock status: UNLOCKED → ENGAGED (green when locked)
- [ ] Source: "simulation" or "mp4"
- [ ] Progress: frame/total and time elapsed
- [ ] **Detection centroid**: shows (x, y) or "—" if none ✓
- [ ] **Estimate position**: shows (x, y) or "—" if no estimate ✓
- [ ] **Estimate offset**: shows distance from boresight or "—"
- [ ] Pan/Tilt: shows current gimbal angles
- [ ] Wall FPS: within ±8% of camera FPS (e.g., 28-32 for 30 Hz) ✓ (G-08)
- [ ] **Loss/Reacq counts**: increment when target lost/reacquired ✓
- [ ] **Retention rate**: shows percentage (e.g., "95.2%") ✓
- [ ] All "—" values are em dashes, never 0 or placeholder ✓ (G-18)

---

## 7. MP4 Video (5 min - G-11)

### Setup
- [ ] Input → Source: select "mp4"
- [ ] Browse MP4: select test.mp4 from prerequisites
- [ ] Probe status: ✅ 640×480  30.0 fps  150 frames
- [ ] Start button: enabled (was disabled before file selected) ✓

### Playback
- [ ] Click Start: video plays
- [ ] Telemetry: Source shows "mp4"
- [ ] Camera view: shows video frames
- [ ] Tracking: pipeline processes video (may or may not track depending on content)
- [ ] Status bar: eventually shows "Reached end-of-stream" ✓ (G-11)
- [ ] Telemetry: Acquisition time `from_first_observable` shows "—" (no ground truth) ✓
- [ ] Loop video: check box, restart: video loops at EOS

### Error Handling
- [ ] Input → Source: mp4, no file selected: Start disabled ✓ (G-11)
- [ ] Browse to non-existent file: Error message, Start disabled
- [ ] Browse to corrupt file (text file with .mp4 extension): Error message, Start disabled

---

## 8. Configuration Management (5 min - G-12/G-13)

### Config Load/Save
- [ ] File → Save Config: select location, save as test_config.json
- [ ] Change several controls (camera fps, slew rate, disturbances)
- [ ] File → Load Config: select test_config.json
- [ ] All controls revert to saved values ✓ (G-12/G-13)
- [ ] Config editor is single source of truth (verify by checking multiple widgets sync)

### Config Validation
- [ ] Camera FPS: set to 25 (below 30): warning appears if allow_below_spec is off
- [ ] Check "Allow <30 FPS": warning disappears
- [ ] Slew rate: set to 11°/s (above max): error appears, config rejected
- [ ] Scan rate: set above slew rate: error appears (scan ≤ slew constraint)
- [ ] Target size: set to 25 (above max 20): error appears

### CLI Integration (G-21)
- [ ] Close GUI
- [ ] Command line: `skylock gui --config test_config.json`
- [ ] GUI opens with loaded config (verify camera FPS matches saved value) ✓

---

## 9. Benchmark Panel (5 min - G-15)

### Scenario Selection
- [ ] Bottom tab: click "Benchmark"
- [ ] Scenario dropdown: shows S01 through S16 (or subset)
- [ ] Select S01_line_clean
- [ ] Seeds field: enter "42"
- [ ] Seed spinbox (Controls panel): automatically updates to 42 ✓ (linked seed G-15)

### Run & Results
- [ ] Click Run: progress bar appears, status shows "Running..."
- [ ] Table populates with row: Scenario | Seed | Verdict | Metrics
- [ ] Verdict: PASS, FAIL, or INDETERMINATE (not blank)
- [ ] Double-click row: detail dialog opens
- [ ] Detail dialog: shows per-requirement metrics (Acquisition, Tracking Error, etc.)
- [ ] Detail dialog: shows PASS/FAIL/INDETERMINATE per requirement ✓ (G-15)
- [ ] Close detail dialog

### S16 External MP4 (G-15)
- [ ] Select S16 (external video)
- [ ] MP4 section appears: "No file selected"
- [ ] Browse MP4: select test.mp4
- [ ] Status: ✅ with file details
- [ ] Click Run: benchmark uses external video ✓ (S16 handled G-15)

### Batch & Export
- [ ] Seeds field: enter "1,2,3,4,5"
- [ ] Click Run: 5 runs execute sequentially
- [ ] Progress: shows X/5 completed ✓ (G-15)
- [ ] Click Cancel (during run): benchmark stops cleanly
- [ ] Export JSON: saves results to file
- [ ] Export Markdown: saves formatted report

---

## 10. Shutdown & Stability (3 min - G-09)

### Normal Close
- [ ] Start session, let run 3 seconds
- [ ] File → Quit (or X button)
- [ ] Window closes immediately
- [ ] No "killTimer" warnings in console ✓ (G-09)
- [ ] No "QThread: Destroyed" warnings ✓ (G-09)

### Close During Run
- [ ] Restart GUI, Start session
- [ ] Immediately click X to close
- [ ] Window closes cleanly within 3 seconds
- [ ] No Qt warnings or errors

### Close During Benchmark
- [ ] Restart GUI, go to Benchmark tab
- [ ] Start benchmark with seeds "1,2,3,4,5"
- [ ] After 1 run completes, close window
- [ ] Window closes cleanly
- [ ] No Qt warnings or errors

---

## 11. Keyboard & Accessibility (3 min)

### Shortcuts
- [ ] Ctrl+R: Starts session
- [ ] Ctrl+.: Stops session
- [ ] Ctrl+Shift+R: Resets session
- [ ] Tab key: cycles focus through controls
- [ ] Tooltips: hover over controls, tooltips appear with units/ranges

### Help Menu
- [ ] Help → About SkyLock: dialog shows version number
- [ ] Help → Keyboard Shortcuts: dialog lists all shortcuts
- [ ] Dialog shows arrow keys and WASD for manual mode

---

## 12. Edge Cases (3 min)

### Invalid Operations
- [ ] Start → Start again: second Start has no effect (button disabled)
- [ ] Stop without Start: no error
- [ ] Reset without Start: no error
- [ ] Load invalid JSON config: error dialog, app keeps running
- [ ] Change config during run: change applies after Stop (or rebuilds session)

### Persistence
- [ ] Change "Show ground truth" to checked
- [ ] Close GUI, reopen: "Show ground truth" still checked
- [ ] Resize window, close, reopen: window size restored
- [ ] View → Reset Layout: clears saved layout

---

## 13. Original Screenshots Scenarios

### Scenario 1: Slew 3.0°/s Valid (G-04)
**Expected:** Slew rate of 3.0°/s is now within valid range (max increased to 10.0°/s).

- [ ] Gimbal → Slew rate: set to 3.0°/s
- [ ] No config error appears
- [ ] Tracking → Scan rate: automatically ≤ 3.0°/s
- [ ] Start: session runs successfully
- [ ] State reaches TRACK within 2 seconds

### Scenario 2: Start State After Config Errors
**Expected:** After fixing config error, Start button re-enables and session runs.

- [ ] Camera → FPS: set to 25 (below spec)
- [ ] "Allow <30 FPS": leave unchecked
- [ ] Start button: disabled (error visible)
- [ ] Check "Allow <30 FPS": error clears
- [ ] Start button: enabled ✓
- [ ] Click Start: session runs successfully
- [ ] State reaches TRACK

---

## Expected Results Summary

At completion, you should have verified:
- ✅ All disturbances apply visible effects without config errors
- ✅ Figure-8 and all shapes (including cross) are selectable and work
- ✅ Slew 3.0°/s is valid (G-04)
- ✅ Low light atmosphere mode is present (G-06)
- ✅ Disabled Start button looks disabled (G-07)
- ✅ Wall FPS is within ±8% of camera FPS (G-08)
- ✅ Clean close with no Qt timer warnings (G-09)
- ✅ Mode switch and manual rates don't reset session (G-10)
- ✅ Manual steering works regardless of focus (G-14)
- ✅ MP4 requires valid file before Start enables (G-11)
- ✅ MP4 playback reaches end-of-stream (G-11)
- ✅ Config is single owner, widgets sync from loaded config (G-12/G-13)
- ✅ Benchmark has linked seed, handles S16, shows progress, per-requirement detail (G-15)
- ✅ Telemetry shows centroids, estimates, detections, loss/reacq/retention (G-16)
- ✅ All None metrics display as "—" not 0 (G-18)
- ✅ Layout is good at both 1100×700 and 1920×1080 (G-20)
- ✅ `skylock gui --config` works (G-21)

---

## Notes

- If any check fails, note the specific step and observed behavior
- Minor visual differences across platforms are acceptable (different fonts, button styles)
- Performance (FPS) may vary by hardware; target is ≥20 FPS average
- Some scenarios (S16) may not be in all builds; verify available scenarios

---

**Checklist Version:** 1.0  
**Created:** 2026-10-01  
**Maintainer:** SkyLock QA Team
