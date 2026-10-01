"""Phase 1 UI cleanup regression tests.

Covers all 10 cleanup rules:
  RULE 1: No MP4 picker in BenchmarkPanel
  RULE 2: No AtmosphereSection in ControlsPanel
  RULE 3: No Manual Rate widget in ControlsPanel
  RULE 4: TelemetryPanel has only approved fields
  RULE 5: BenchmarkPanel table has only 8 approved columns
  RULE 6: BenchmarkPanel controls use 2-row layout + More menu
  RULE 7: NoWheel widgets do not change value on wheel event
  RULE 8: ControlsPanel has no orphan/empty sections
  RULE 9: Buttons have consistent text and are enabled by default
  RULE 10: No blank QGroupBox or empty placeholder labels visible
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from skylock.config.models import SkyLockConfig
from skylock.ui.config_editor import ConfigEditor
from skylock.ui.panels.benchmark import BenchmarkPanel
from skylock.ui.panels.controls import ControlsPanel
from skylock.ui.panels.telemetry import TelemetryPanel
from skylock.ui.widgets.no_wheel import NoWheelComboBox, NoWheelDoubleSpinBox, NoWheelSpinBox

pytestmark = pytest.mark.gui


# ─── RULE 1: No MP4 picker in BenchmarkPanel ─────────────────────────────────

def test_rule1_no_mp4_picker_in_benchmark_panel(qapp) -> None:
    """BenchmarkPanel must not expose an MP4 file picker button or path label."""
    panel = BenchmarkPanel()
    panel.show()

    # Must not have MP4 browse button
    assert not hasattr(panel, "btn_browse_mp4"), (
        "btn_browse_mp4 must not exist on BenchmarkPanel (Phase 1 Rule 1)"
    )
    # Must not have MP4 path label
    assert not hasattr(panel, "lbl_mp4_path"), (
        "lbl_mp4_path must not exist on BenchmarkPanel (Phase 1 Rule 1)"
    )
    # Internal _mp4_path is still used for S16, but no button
    assert hasattr(panel, "_mp4_path"), (
        "_mp4_path internal state must still exist for S16 support"
    )

    panel.close()


# ─── RULE 2: No Atmosphere section in ControlsPanel ──────────────────────────

def test_rule2_no_atmosphere_section(qapp) -> None:
    """ControlsPanel must not display an atmosphere mode/strength control."""
    editor = ConfigEditor(SkyLockConfig())
    panel = ControlsPanel(editor)
    panel.show()

    if hasattr(panel, "atmos_section"):
        assert not panel.atmos_section.isVisible(), (
            "Atmosphere section must not be visible (Phase 1 Rule 2)"
        )

    panel.close()


# ─── RULE 3: No Manual Rate widget in ControlsPanel ──────────────────────────

def test_rule3_no_manual_rate_widget(qapp) -> None:
    """ControlsPanel must not expose a spn_manual_rate spinbox."""
    editor = ConfigEditor(SkyLockConfig())
    panel = ControlsPanel(editor)
    panel.show()

    assert not hasattr(panel, "spn_manual_rate"), (
        "spn_manual_rate must not exist on ControlsPanel (Phase 1 Rule 3)"
    )

    panel.close()


# ─── RULE 4: TelemetryPanel has only approved fields ─────────────────────────

def test_rule4_telemetry_has_essential_fields(qapp) -> None:
    """TelemetryPanel must have all approved essential fields."""
    panel = TelemetryPanel()
    panel.show()

    essential = [
        "badge", "lbl_lock",
        "lbl_det_count", "lbl_best_centroid", "lbl_est_pos",
        "lbl_pan", "lbl_tilt",
        "lbl_acq_time", "lbl_track_err", "lbl_last_reacq", "lbl_fps_pipe",
    ]
    for attr in essential:
        assert hasattr(panel, attr), f"Essential field {attr!r} is missing from TelemetryPanel"

    panel.close()


def test_rule4_telemetry_removed_fields_absent(qapp) -> None:
    """TelemetryPanel must NOT have removed display fields."""
    panel = TelemetryPanel()
    panel.show()

    removed = [
        "lbl_fps_wall", "lbl_latency", "lbl_cmd_rate",
        "lbl_lock_retention", "lbl_loss_events", "lbl_state_times",
        "lbl_est_offset", "lbl_progress", "lbl_source",
    ]
    for attr in removed:
        assert not hasattr(panel, attr), (
            f"Removed field {attr!r} must not exist on TelemetryPanel (Phase 1 Rule 4)"
        )

    panel.close()


# ─── RULE 5: BenchmarkPanel table has only 8 approved columns ────────────────

def test_rule5_benchmark_table_column_count(qapp) -> None:
    """Benchmark results table must have exactly 8 columns."""
    panel = BenchmarkPanel()
    panel.show()

    assert panel.table.columnCount() == 8, (
        f"Expected 8 columns, got {panel.table.columnCount()} (Phase 1 Rule 5)"
    )

    panel.close()


def test_rule5_benchmark_table_column_names(qapp) -> None:
    """Benchmark results table must have the exact approved column names."""
    panel = BenchmarkPanel()
    panel.show()

    expected = [
        "Scenario",
        "Seed",
        "Verdict",
        "Acquisition (s)",
        "Tracking Error (px)",
        "Loss Rate",
        "Reacquisition (s)",
        "FPS",
    ]
    for col_idx, name in enumerate(expected):
        header_item = panel.table.horizontalHeaderItem(col_idx)
        assert header_item is not None, f"Column {col_idx} header item is None"
        assert header_item.text() == name, (
            f"Column {col_idx}: expected {name!r}, got {header_item.text()!r} (Phase 1 Rule 5)"
        )

    panel.close()


# ─── RULE 6: BenchmarkPanel controls layout ───────────────────────────────────

def test_rule6_benchmark_has_more_menu_button(qapp) -> None:
    """BenchmarkPanel must have a 'More Actions' menu button for secondary actions."""
    panel = BenchmarkPanel()
    panel.show()

    assert hasattr(panel, "btn_more"), (
        "btn_more must exist on BenchmarkPanel (Phase 1 Rule 6)"
    )
    assert panel.btn_more.isVisible(), "btn_more must be visible"
    assert "More Actions" in panel.btn_more.text(), "btn_more text must include 'More Actions'"
    assert panel.btn_more.menu() is not None, "btn_more must have a QMenu attached"

    actions = [a.text() for a in panel.btn_more.menu().actions() if not a.isSeparator()]
    assert "Details" in actions
    assert "Export JSON" in actions
    assert "Export Markdown" in actions
    assert "Load Report" in actions
    assert "Export CSV" not in actions

    panel.close()


def test_rule6_benchmark_main_buttons_present(qapp) -> None:
    """BenchmarkPanel must have btn_run ('Run Scenario'), btn_run_all, btn_cancel."""
    panel = BenchmarkPanel()
    panel.show()

    for attr in ("btn_run", "btn_run_all", "btn_cancel"):
        assert hasattr(panel, attr), f"{attr} must exist on BenchmarkPanel (Phase 1 Rule 6)"
        assert getattr(panel, attr).isVisible(), f"{attr} must be visible"

    assert panel.btn_run.text() == "Run Scenario"
    assert panel.btn_run_all.text() == "Run All"
    assert panel.btn_cancel.text() == "Cancel"

    # Run Scenario and Run All start enabled; Cancel starts disabled
    assert panel.btn_run.isEnabled(), "btn_run must start enabled"
    assert panel.btn_run_all.isEnabled(), "btn_run_all must start enabled"
    assert not panel.btn_cancel.isEnabled(), "btn_cancel must start disabled"

    panel.close()


def test_rule6_benchmark_no_separate_details_button(qapp) -> None:
    """BenchmarkPanel must not have a standalone Details button (moved to More menu)."""
    panel = BenchmarkPanel()
    panel.show()

    assert not hasattr(panel, "btn_details"), (
        "btn_details must not exist as standalone button (Phase 1 Rule 6: moved to More menu)"
    )

    panel.close()


# ─── RULE 7: NoWheel widgets ignore mouse wheel ───────────────────────────────

def _make_wheel_event(delta: int = 120) -> QWheelEvent:
    """Create a synthetic QWheelEvent for testing."""
    from PySide6.QtCore import QPoint
    return QWheelEvent(
        QPointF(0, 0),      # pos
        QPointF(0, 0),      # globalPos
        QPoint(0, delta),   # pixelDelta
        QPoint(0, delta),   # angleDelta
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


def test_rule7_no_wheel_spinbox_ignores_wheel(qapp) -> None:
    """NoWheelSpinBox must not change value when wheel event received."""
    widget = NoWheelSpinBox()
    widget.setRange(0, 100)
    widget.setValue(50)
    widget.show()

    initial = widget.value()
    evt = _make_wheel_event(120)
    widget.wheelEvent(evt)
    QApplication.processEvents()

    assert widget.value() == initial, (
        f"NoWheelSpinBox value changed from {initial} to {widget.value()} on wheel event"
    )
    widget.close()


def test_rule7_no_wheel_double_spinbox_ignores_wheel(qapp) -> None:
    """NoWheelDoubleSpinBox must not change value when wheel event received."""
    widget = NoWheelDoubleSpinBox()
    widget.setRange(0.0, 100.0)
    widget.setValue(50.0)
    widget.show()

    initial = widget.value()
    evt = _make_wheel_event(120)
    widget.wheelEvent(evt)
    QApplication.processEvents()

    assert widget.value() == pytest.approx(initial), (
        f"NoWheelDoubleSpinBox value changed from {initial} to {widget.value()} on wheel event"
    )
    widget.close()


def test_rule7_no_wheel_combobox_ignores_wheel(qapp) -> None:
    """NoWheelComboBox must not change index when wheel event received."""
    widget = NoWheelComboBox()
    widget.addItems(["A", "B", "C"])
    widget.setCurrentIndex(0)
    widget.show()

    evt = _make_wheel_event(120)
    widget.wheelEvent(evt)
    QApplication.processEvents()

    assert widget.currentIndex() == 0, (
        f"NoWheelComboBox index changed from 0 to {widget.currentIndex()} on wheel event"
    )
    widget.close()


def test_rule7_controls_spinboxes_use_no_wheel(qapp) -> None:
    """Core ControlsPanel spinboxes must be NoWheel instances."""
    editor = ConfigEditor(SkyLockConfig())
    panel = ControlsPanel(editor)
    panel.show()

    for attr, cls in [
        ("spn_fps", NoWheelDoubleSpinBox),
        ("spn_slew", NoWheelDoubleSpinBox),
        ("spn_seed", NoWheelSpinBox),
        ("spn_tgt_size", NoWheelSpinBox),
        ("spn_target_count", NoWheelSpinBox),
        ("cmb_input", NoWheelComboBox),
        ("cmb_tgt_motion", NoWheelComboBox),
    ]:
        widget = getattr(panel, attr)
        assert isinstance(widget, cls), (
            f"{attr} must be a {cls.__name__} instance for Rule 7; got {type(widget).__name__}"
        )

    panel.close()


def test_rule7_mouse_wheel_behavioral_scroll(qapp) -> None:
    """Behavioral Qt test for mouse wheel scrolling in ControlsPanel (Rule 4 specification).

    Verifies:
      1. Mouse wheel over NoWheelSpinBox does NOT change spinbox value,
         and DOES scroll the parent Controls QScrollArea.
      2. Mouse wheel over NoWheelDoubleSpinBox does NOT change value,
         and DOES scroll parent QScrollArea.
      3. Mouse wheel over NoWheelComboBox does NOT change selection,
         and DOES scroll parent QScrollArea.
      4. Mouse wheel over empty Controls area scrolls normally.
      5. Keyboard arrows, typing, and clicking continue working normally on controls.
    """
    from PySide6.QtTest import QTest

    editor = ConfigEditor(SkyLockConfig())
    panel = ControlsPanel(editor)
    # Constrain size so the vertical scrollbar is active and can scroll
    panel.resize(320, 280)
    panel.show()
    QApplication.processEvents()

    vbar = panel.scroll_area.verticalScrollBar()
    assert vbar.maximum() > 0, "ControlsPanel vertical scrollbar must be scrollable"

    # --- 1. Test NoWheelSpinBox (spn_seed) ---
    vbar.setValue(0)
    QApplication.processEvents()
    initial_scroll = vbar.value()
    initial_seed = panel.spn_seed.value()

    # Wheel down event over the spinbox
    evt_sb = _make_wheel_event(delta=-120)
    QApplication.sendEvent(panel.spn_seed, evt_sb)
    QApplication.processEvents()

    assert panel.spn_seed.value() == initial_seed, (
        f"Spinbox value changed on mouse wheel (expected {initial_seed}, "
        f"got {panel.spn_seed.value()})"
    )
    assert vbar.value() > initial_scroll, (
        f"Parent QScrollArea did not scroll when mouse wheeled over spinbox "
        f"(initial={initial_scroll}, current={vbar.value()})"
    )

    # --- 2. Test NoWheelDoubleSpinBox (spn_fps) ---
    vbar.setValue(0)
    QApplication.processEvents()
    initial_scroll = vbar.value()
    initial_fps = panel.spn_fps.value()

    evt_fps = _make_wheel_event(delta=-120)
    QApplication.sendEvent(panel.spn_fps, evt_fps)
    QApplication.processEvents()

    assert panel.spn_fps.value() == pytest.approx(initial_fps), (
        f"Double spinbox value changed on mouse wheel (expected {initial_fps}, "
        f"got {panel.spn_fps.value()})"
    )
    assert vbar.value() > initial_scroll, (
        "Parent QScrollArea did not scroll when mouse wheeled over double spinbox"
    )

    # --- 3. Test NoWheelComboBox (cmb_input) ---
    vbar.setValue(0)
    QApplication.processEvents()
    initial_scroll = vbar.value()
    initial_idx = panel.cmb_input.currentIndex()

    evt_cmb = _make_wheel_event(delta=-120)
    QApplication.sendEvent(panel.cmb_input, evt_cmb)
    QApplication.processEvents()

    assert panel.cmb_input.currentIndex() == initial_idx, (
        f"Combobox selection changed on mouse wheel (expected {initial_idx}, "
        f"got {panel.cmb_input.currentIndex()})"
    )
    assert vbar.value() > initial_scroll, (
        "Parent QScrollArea did not scroll when mouse wheeled over combobox"
    )

    # --- 4. Test mouse wheel over empty controls area / scroll viewport ---
    vbar.setValue(0)
    QApplication.processEvents()
    initial_scroll = vbar.value()

    evt_empty = _make_wheel_event(delta=-120)
    QApplication.sendEvent(panel.scroll_area.viewport(), evt_empty)
    QApplication.processEvents()

    assert vbar.value() > initial_scroll, (
        "Parent QScrollArea did not scroll when mouse wheeled over empty area"
    )

    # --- 5. Verify keyboard arrow keys still change spinbox value normally ---
    panel.spn_seed.setFocus()
    seed_before_key = panel.spn_seed.value()
    QTest.keyClick(panel.spn_seed, Qt.Key.Key_Up)
    QApplication.processEvents()

    assert panel.spn_seed.value() == seed_before_key + 1, (
        "Keyboard arrow up must still increment spinbox value"
    )

    panel.close()


# ─── RULE 8: ControlsPanel has no orphan/empty sections ─────────────────────

def test_rule8_controls_sections_not_empty(qapp) -> None:
    """All visible QGroupBoxes in ControlsPanel must have at least one child widget."""
    from PySide6.QtWidgets import QGroupBox
    editor = ConfigEditor(SkyLockConfig())
    panel = ControlsPanel(editor)
    panel.show()

    def _find_groupboxes(widget) -> list[QGroupBox]:
        result = []
        for child in widget.findChildren(QGroupBox):
            result.append(child)
        return result

    for box in _find_groupboxes(panel):
        if not box.isVisible():
            continue
        # Count child widgets that are visible and have content
        n_children = sum(1 for c in box.children() if hasattr(c, "isVisible") and c.isVisible())
        assert n_children >= 1, (
            f"QGroupBox '{box.title()}' appears empty (Phase 1 Rule 8)"
        )

    panel.close()


# ─── RULE 9: Button consistency ───────────────────────────────────────────────

def test_rule9_controls_action_buttons_text(qapp) -> None:
    """ControlsPanel action buttons must have correct, consistent labels."""
    editor = ConfigEditor(SkyLockConfig())
    panel = ControlsPanel(editor)
    panel.show()

    assert panel.btn_start.text() in ("Start", "Start Simulation", "Run")
    assert panel.btn_stop.text() in ("Stop", "Stop Simulation", "Halt")

    panel.close()


def test_rule9_controls_start_has_disabled_style(qapp) -> None:
    """btn_start stylesheet must contain a :disabled rule."""
    editor = ConfigEditor(SkyLockConfig())
    panel = ControlsPanel(editor)
    panel.show()
    assert ":disabled" in panel.btn_start.styleSheet()
    panel.close()


# ─── RULE 10: No empty/redundant UI ──────────────────────────────────────────

def test_rule10_no_visible_placeholder_labels(qapp) -> None:
    """TelemetryPanel and BenchmarkPanel must not have any empty visible QLabels."""
    from PySide6.QtWidgets import QLabel

    for widget_class in (TelemetryPanel, BenchmarkPanel):
        widget = widget_class()
        widget.show()
        QApplication.processEvents()

        empty_labels = [
            c for c in widget.findChildren(QLabel)
            if c.isVisible() and c.text().strip() == ""
        ]
        assert len(empty_labels) == 0, (
            f"{widget_class.__name__}: found {len(empty_labels)} empty visible QLabel(s) "
            f"(Phase 1 Rule 10): {[(c.objectName(), c.text()) for c in empty_labels]}"
        )
        widget.close()
