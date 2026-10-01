# Phase G6: Professional Layout & Dark Theme - Implementation Report

## Summary

Phase G6 has been successfully implemented, delivering a professional, stable layout with a unified dark theme for the SkyLock GUI. All acceptance criteria have been met, and comprehensive tests verify the implementation.

## Files Created

### Core Implementation
- **src/skylock/ui/theme.py** (260 lines)
  - Centralized dark theme with Fusion style
  - All colour constants (base palette, state colours, verdict colours, overlay colours)
  - Global stylesheet for QGroupBox, QPushButton, QTableWidget, QToolTip, scrollbars, tabs
  - `apply_theme()` function sets palette and stylesheets

- **src/skylock/ui/settings.py** (129 lines)
  - `AppSettings` class wrapping QSettings
  - Persist/restore window geometry, dock state, splitter sizes
  - Last-used directories for MP4/config file dialogs
  - Show ground truth and legend flags
  - Layout reset functionality

### Tests
- **tests/ui/test_g6_theme_layout.py** (294 lines)
  - 14 comprehensive tests covering theme, layout, settings, menu actions
  - Screenshot generation at 1280x800 for visual verification
  - All tests pass headlessly (QT_QPA_PLATFORM=offscreen)

## Files Modified

### Major Updates
- **src/skylock/ui/main_window.py**
  - Replaced bottom dock with QTabWidget containing Benchmark tab
  - Vertical QSplitter: camera view (top, 60%+ height) + tabs (bottom, collapsible)
  - Menu bar: File (Load/Save config, Export benchmark), Run (Start/Stop/Reset with shortcuts), View (dock toggles, GT/Legend, Reset layout), Help (About, Shortcuts dialog)
  - Status bar with permanent widgets: state, source, frame count, FPS, pending config indicator
  - Dock widgets: minimum widths (Controls 340px, Telemetry 280px), closable
  - Settings integration: restore/save on startup/close
  - Theme application in `run_app()`

### Theme Integration (Removed All Hard-Coded Colours)
- **src/skylock/ui/widgets/camera_view.py** - Import theme, use overlay colour constants
- **src/skylock/ui/widgets/state_badge.py** - Use state colour constants from theme
- **src/skylock/ui/widgets/state_timeline.py** - Use theme colours
- **src/skylock/ui/panels/benchmark.py** - Use verdict and status colours from theme
- **src/skylock/ui/panels/benchmark_detail.py** - Use verdict colours
- **src/skylock/ui/panels/controls.py** - Use button and error colours from theme
- **src/skylock/ui/panels/controls_sections.py** - Use status colours
- **src/skylock/ui/panels/telemetry.py** - Use status and text colours from theme

### Other
- **.gitignore** - Added `tests/ui/_artifacts/` to ignore screenshot directory

## Test Results

All 14 G6 tests pass:

```
tests/ui/test_g6_theme_layout.py::test_theme_applied_without_exceptions PASSED
tests/ui/test_g6_theme_layout.py::test_main_window_constructs_at_minimum_size PASSED
tests/ui/test_g6_theme_layout.py::test_main_window_constructs_at_1920x1080 PASSED
tests/ui/test_g6_theme_layout.py::test_layout_defaults_camera_dominant PASSED
tests/ui/test_g6_theme_layout.py::test_settings_round_trip PASSED
tests/ui/test_g6_theme_layout.py::test_menu_actions_exist_and_connected PASSED
tests/ui/test_g6_theme_layout.py::test_reset_action_triggers_signal PASSED
tests/ui/test_g6_theme_layout.py::test_no_hex_colour_literals_outside_theme PASSED
tests/ui/test_g6_theme_layout.py::test_screenshot_generation PASSED
tests/ui/test_g6_theme_layout.py::test_status_bar_permanent_widgets PASSED
tests/ui/test_g6_theme_layout.py::test_tab_widget_contains_benchmark PASSED
tests/ui/test_g6_theme_layout.py::test_docks_are_closable_and_restorable PASSED
tests/ui/test_g6_theme_layout.py::test_minimum_dock_widths PASSED
tests/ui/test_g6_theme_layout.py::test_tooltips_on_controls PASSED

14 passed in 104.00s
```

**Lint Check:** All files pass `ruff check` with no errors.

**Screenshot:** Generated at `tests/ui/_artifacts/main_window.png` (1280x800 resolution)

## Acceptance Criteria Met

✅ **At 1280x800, camera view is dominant element**
- Camera area occupies >= 55% of window height (verified in test)
- Controls and telemetry fully reachable (minimum widths enforced)
- No clipped group boxes at 1100x700 minimum size

✅ **One palette, colours defined only in theme.py**
- All 80+ hex colour constants moved to theme.py
- Zero hex literals found in ui/ code outside theme.py (verified by test)
- Consistent dark theme across all widgets

✅ **Window/dock/splitter state restored across runs**
- AppSettings persists geometry, dock state, splitter sizes
- Last-used directories remembered
- Show GT and Legend flags persisted

✅ **All menu actions work; shortcuts documented**
- File menu: Load/Save config, Export benchmarks (JSON/Markdown), Quit
- Run menu: Start (Ctrl+R), Stop (Ctrl+.), Reset (Ctrl+Shift+R)
- View menu: Dock toggles, Show GT, Show Legend, Reset Layout
- Help menu: About (displays version), Keyboard Shortcuts dialog
- All actions wired to existing signals/slots (verified in tests)

## Implementation Details

### Theme System
- **Fusion style** with custom dark QPalette
- **Base colours:** Window #111827, Base #0B1220, Text #E5E7EB, Highlight #2563EB
- **State colours:** Search (blue), Acquire (amber), Track (emerald), Lost (rose), Reacquire (orange)
- **Verdict colours:** Pass (dark green), Fail (dark red), Indeterminate (dark amber), Not Run (gray)
- **Overlay colours:** Boresight, Detection, Gate, Estimate, Ground Truth (all with appropriate alpha)
- **Global stylesheet:** Styled QGroupBox titles, disabled buttons, tables, tooltips, scrollbars, tabs

### Layout Structure
```
MainWindow (1100x700 min, 1280x800 default)
├── Menu Bar (File, Run, View, Help)
├── Central Widget: QSplitter (Vertical)
│   ├── Top (stretch 10): Camera View + State Timeline + Toolbar
│   └── Bottom (stretch 1, 220px default): QTabWidget
│       └── Tab "Benchmark": BenchmarkPanel
├── Left Dock: Controls (340px min, closable/movable)
├── Right Dock: Telemetry (280px min, closable/movable)
└── Status Bar: State | Source | Frame | FPS | Pending
```

### Accessibility Features
- Tooltips on all controls with units and limits
- Tab order for keyboard navigation
- Keyboard shortcuts: Ctrl+R (Start), Ctrl+. (Stop), Ctrl+Shift+R (Reset)
- Manual control mode: Arrow keys and WASD (documented in Help menu)
- Minimum font size 11px (enforced by not using smaller sizes)
- High-DPI support (automatic in Qt6)

## Known Limitations

1. **No New Behaviour:** Phase strictly implements layout/theme changes. No functionality changes to worker, pacing, or config logic.

2. **Manual Testing Required:** Full WCAG compliance requires manual testing with assistive technologies and expert accessibility review (per instructions).

3. **Platform Differences:** Theme rendering may vary slightly across Windows/macOS/Linux due to platform-specific Qt rendering, but Fusion style minimizes this.

4. **Thread Warning:** QThread cleanup warning appears during test shutdown (non-critical, does not affect functionality).

## Migration Notes

Users upgrading from previous versions will experience:
- Layout reset on first launch (settings won't restore old dock positions)
- New dark theme automatically applied
- Benchmark moved from bottom dock to bottom tab
- New keyboard shortcuts active
- Settings persisted going forward

## Conclusion

Phase G6 successfully delivers a professional, accessible, and maintainable GUI with:
- **Consistent dark theme** across all UI elements
- **Professional layout** with dominant camera view
- **Persistent settings** for window state and preferences
- **Complete menu system** with keyboard shortcuts
- **Zero hard-coded colours** outside theme.py
- **Comprehensive test coverage** (14 tests, all passing)
- **Clean code** (passes ruff with no errors)

The implementation follows all GLOBAL RULES, uses only verified config keys, adds no placeholder stubs, and maintains backward compatibility with existing public APIs.
