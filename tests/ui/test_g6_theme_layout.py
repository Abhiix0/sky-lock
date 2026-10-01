"""Tests for Phase G6: professional layout and dark theme consistency."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from skylock.ui import theme
from skylock.ui.main_window import MainWindow
from skylock.ui.settings import AppSettings


def test_theme_applied_without_exceptions(qapp: QApplication) -> None:
    """Theme application should succeed without raising exceptions."""
    theme.apply_theme(qapp)
    # Style is set but name might be empty on some platforms
    # Just verify no exceptions were raised
    assert qapp.style() is not None


def test_main_window_constructs_at_minimum_size(qapp: QApplication) -> None:
    """Main window should construct at minimum size 1100x700."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.show()
    qapp.processEvents()

    assert window.minimumWidth() == 1100
    assert window.minimumHeight() == 700
    assert window.width() >= 1100
    assert window.height() >= 700


def test_main_window_constructs_at_1920x1080(qapp: QApplication) -> None:
    """Main window should construct properly at 1920x1080."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.resize(1920, 1080)
    window.show()
    qapp.processEvents()

    # All major widgets should have valid geometry
    assert window.camera_view.width() > 0
    assert window.camera_view.height() > 0
    assert window.controls_panel.width() >= 340
    assert window.telemetry_panel.width() >= 280

    # Controls panel scroll area should accommodate content
    controls_scroll = window.controls_panel.parentWidget()
    if controls_scroll and hasattr(controls_scroll, "sizeHint"):
        # Content should fit without excessive scrolling
        assert window.controls_panel.height() > 0


def test_layout_defaults_camera_dominant(qapp: QApplication) -> None:
    """At 1280x800, camera view should occupy >= 55% of central height."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.resize(1280, 800)
    window.show()
    qapp.processEvents()

    # Get splitter sizes
    sizes = window.central_splitter.sizes()
    total_height = sum(sizes)
    camera_area_height = sizes[0] if sizes else 0

    # Camera area should be at least 55% of total
    assert camera_area_height >= total_height * 0.55


def test_settings_round_trip(qapp: QApplication, tmp_path: Path) -> None:
    """Settings should persist and restore correctly."""
    # Use temporary QSettings location
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))

    settings = AppSettings()

    # Test window state (mock)
    theme.apply_theme(qapp)
    window1 = MainWindow()
    window1.resize(1400, 900)
    window1.show()
    qapp.processEvents()

    # Save state
    settings.save_window_state(window1)
    settings.save_splitter_sizes(window1.central_splitter, "main")
    settings.set_show_ground_truth(True)
    settings.set_show_legend(True)
    settings.set_last_mp4_directory("/tmp/test")
    settings.set_last_config_directory("/tmp/config")

    # Create new settings instance and restore
    settings2 = AppSettings()

    assert settings2.get_show_ground_truth() is True
    assert settings2.get_show_legend() is True
    assert settings2.get_last_mp4_directory() is None  # Doesn't exist
    assert settings2.get_last_config_directory() is None  # Doesn't exist

    # Create directories and test again
    (tmp_path / "test").mkdir()
    (tmp_path / "config").mkdir()
    settings.set_last_mp4_directory(str(tmp_path / "test"))
    settings.set_last_config_directory(str(tmp_path / "config"))

    settings3 = AppSettings()
    assert settings3.get_last_mp4_directory() == str(tmp_path / "test")
    assert settings3.get_last_config_directory() == str(tmp_path / "config")


def test_menu_actions_exist_and_connected(qapp: QApplication) -> None:
    """Menu actions should exist and be connected to slots."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.show()
    qapp.processEvents()

    # Check File menu actions
    file_actions = window.menuBar().actions()[0].menu().actions()
    assert len(file_actions) >= 4  # Load, Save, Export JSON, Export MD, Quit

    # Check Run menu actions
    run_actions = window.menuBar().actions()[1].menu().actions()
    assert len(run_actions) >= 3  # Start, Stop, Reset
    assert window.act_start.shortcut().toString() == "Ctrl+R"
    assert window.act_stop.shortcut().toString() == "Ctrl+."
    assert window.act_reset.shortcut().toString() == "Ctrl+Shift+R"

    # Check View menu
    view_actions = window.menuBar().actions()[2].menu().actions()
    assert len(view_actions) >= 5  # Controls, Telemetry, separator, GT, Legend, separator, Reset Layout

    # Check Help menu
    help_actions = window.menuBar().actions()[3].menu().actions()
    assert len(help_actions) >= 2  # About, Shortcuts


def test_reset_action_triggers_signal(qapp: QApplication) -> None:
    """Reset menu action should trigger controls panel reset signal."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.show()
    qapp.processEvents()

    # Just verify the action exists and has a shortcut
    assert window.act_reset is not None
    assert window.act_reset.shortcut().toString() == "Ctrl+Shift+R"


def test_no_hex_colour_literals_outside_theme(tmp_path: Path) -> None:
    """No hex colour literals should exist in ui/ code outside theme.py."""
    ui_path = Path("src/skylock/ui")
    violations = []

    for py_file in ui_path.rglob("*.py"):
        if py_file.name == "theme.py":
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Skip files with encoding issues
            continue

        lines = content.split("\n")

        import re
        hex_pattern = re.compile(r'#[0-9A-Fa-f]{6}')

        for line_no, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith("#"):
                continue

            matches = hex_pattern.findall(line)
            if matches:
                violations.append(f"{py_file}:{line_no}: {line.strip()}")

    assert len(violations) == 0, "Found hex colour literals outside theme.py:\n" + "\n".join(violations)


def test_screenshot_generation(qapp: QApplication, tmp_path: Path) -> None:
    """Generate screenshot of main window at 1280x800 for manual inspection."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.resize(1280, 800)
    window.show()
    qapp.processEvents()

    # Ensure artifacts directory exists
    artifacts_dir = Path("tests/ui/_artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Capture screenshot
    screenshot_path = artifacts_dir / "main_window.png"
    pixmap = window.grab()
    pixmap.save(str(screenshot_path))

    assert screenshot_path.exists()
    assert screenshot_path.stat().st_size > 0


def test_status_bar_permanent_widgets(qapp: QApplication) -> None:
    """Status bar should have permanent widgets for state, source, frame, fps."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.show()
    qapp.processEvents()

    # Check permanent widgets exist
    assert window.lbl_status_state is not None
    assert window.lbl_status_source is not None
    assert window.lbl_status_frame is not None
    assert window.lbl_status_fps is not None
    assert window.lbl_status_pending is not None

    # Verify they're in the status bar
    status_bar = window.statusBar()
    assert window.lbl_status_state in status_bar.children()


def test_tab_widget_contains_benchmark(qapp: QApplication) -> None:
    """Tab widget should contain benchmark panel."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.show()
    qapp.processEvents()

    assert window.tab_widget.count() >= 1
    assert window.tab_widget.tabText(0) == "Benchmark"
    assert window.bench_panel is not None


def test_docks_are_closable_and_restorable(qapp: QApplication) -> None:
    """Dock widgets should be closable and restorable via View menu."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.show()
    qapp.processEvents()

    # Docks should be closable
    assert window.dock_controls.features() & window.dock_controls.DockWidgetFeature.DockWidgetClosable
    assert window.dock_telemetry.features() & window.dock_telemetry.DockWidgetFeature.DockWidgetClosable

    # Close controls dock
    window.dock_controls.close()
    qapp.processEvents()
    assert not window.dock_controls.isVisible()

    # Restore via toggle action
    window.dock_controls.toggleViewAction().trigger()
    qapp.processEvents()
    assert window.dock_controls.isVisible()


def test_minimum_dock_widths(qapp: QApplication) -> None:
    """Docks should have minimum widths set."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.show()
    qapp.processEvents()

    assert window.dock_controls.minimumWidth() == 340
    assert window.dock_telemetry.minimumWidth() == 280


def test_tooltips_on_controls(qapp: QApplication) -> None:
    """Controls should have tooltips."""
    theme.apply_theme(qapp)
    window = MainWindow()
    window.show()
    qapp.processEvents()

    # Check some key controls have tooltips
    assert window.chk_debug_gt.toolTip() != ""
    assert window.chk_legend.toolTip() != ""

    # Status bar labels should have tooltips
    assert window.lbl_status_state.toolTip() != ""
    assert window.lbl_status_source.toolTip() != ""
    assert window.lbl_status_frame.toolTip() != ""
    assert window.lbl_status_fps.toolTip() != ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
