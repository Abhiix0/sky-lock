"""Comprehensive G3 controls panel tests.

Covers: parametrized slider/spin range validation, presets apply/sync,
target count changes, motion pages, MP4 validation, save/load round-trip,
and ``skylock gui --config bad.json`` exit code.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from skylock.config.io import from_json, to_dict, to_json
from skylock.config.models import SkyLockConfig
from skylock.ui.config_editor import ConfigEditor
from skylock.ui.panels.controls import ControlsPanel

pytestmark = pytest.mark.gui

# ───────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def controls(qapp):  # noqa: ANN001
    """Fresh ControlsPanel backed by a default SkyLockConfig, shown offscreen."""
    editor = ConfigEditor(SkyLockConfig())
    panel = ControlsPanel(editor)
    panel.show()
    yield panel
    panel.close()


# ───────────────────────────────────────────────────────────────────
# 1.  Parametrized min/max range validation
# ───────────────────────────────────────────────────────────────────

# Each entry: (widget_attr, min_val, max_val)
# These are the spin boxes and their spec limits.
_WIDGET_RANGES: list[tuple[str, float, float]] = [
    ("spn_fps", 30.0, 120.0),
    ("spn_slew", 0.1, 10.0),
    ("spn_seed", 0, 999999),
    ("spn_tgt_size", 5, 20),
    ("spn_target_count", 1, 4),
    ("spn_manual_rate", 0.1, 10.0),
]


@pytest.mark.parametrize("attr,min_v,max_v", _WIDGET_RANGES, ids=[r[0] for r in _WIDGET_RANGES])
def test_widget_min_max_valid(controls, attr: str, min_v: float, max_v: float) -> None:  # noqa: ANN001
    """Setting a widget to its min and max must not produce a config error."""
    widget = getattr(controls, attr)

    # Test minimum
    widget.setValue(min_v)
    QApplication.processEvents()
    assert not controls._has_violations(), (
        f"{attr}={min_v} produced violation"
    )

    # Test maximum
    widget.setValue(max_v)
    QApplication.processEvents()
    assert not controls._has_violations(), (
        f"{attr}={max_v} produced violation"
    )


# ───────────────────────────────────────────────────────────────────
# 2.  Disturbance magnitude rows at min/max
# ───────────────────────────────────────────────────────────────────

_DIST_RANGES: list[tuple[str, float, float]] = [
    ("dist_gaussian", 0.0, 20.0),
    ("dist_salt_pepper", 0.0, 1.0),
    ("dist_poisson", 0.01, 100.0),
    ("dist_jitter", 0.0, 20.0),
    ("dist_drift", 0.0, 20.0),
    ("dist_blur", 0.0, 10.0),
]


@pytest.mark.parametrize(
    "attr,min_v,max_v", _DIST_RANGES, ids=[r[0] for r in _DIST_RANGES]
)
def test_disturbance_row_range(controls, attr: str, min_v: float, max_v: float) -> None:  # noqa: ANN001
    """Disturbance magnitude at min and max must not produce validation errors."""
    row = getattr(controls, attr)

    # Enable it first
    row.chk.setChecked(True)
    QApplication.processEvents()

    # Min
    row.spin.setValue(min_v)
    QApplication.processEvents()
    assert not controls._has_violations(), (
        f"{attr} min={min_v} produced violation"
    )

    # Max
    row.spin.setValue(max_v)
    QApplication.processEvents()
    assert not controls._has_violations(), (
        f"{attr} max={max_v} produced violation"
    )


# ───────────────────────────────────────────────────────────────────
# 3.  Presets apply and sync back
# ───────────────────────────────────────────────────────────────────

_PRESETS = [
    "preset_clear",
    "preset_haze",
    "preset_fog",
    "preset_rain",
    "preset_low_light",
    "preset_spec_max_noise",
    "preset_spec_max_jitter",
]


@pytest.mark.parametrize("preset_fn", _PRESETS)
def test_preset_applies(controls, preset_fn: str) -> None:  # noqa: ANN001
    """Each preset must apply without config errors and update widgets."""
    controls._on_preset_selected(preset_fn)
    QApplication.processEvents()
    assert not controls._has_violations(), (
        f"Preset {preset_fn} produced violations"
    )


# ───────────────────────────────────────────────────────────────────
# 4.  Target count 1 → 3 → 2
# ───────────────────────────────────────────────────────────────────

def test_target_count_changes(controls) -> None:  # noqa: ANN001
    """Target count adjustments must produce valid configs."""
    controls.spn_target_count.setValue(1)
    QApplication.processEvents()
    assert controls.editor.config.target.count == 1

    controls.spn_target_count.setValue(3)
    QApplication.processEvents()
    assert not controls._has_violations()
    assert controls.editor.config.target.count == 3
    assert len(controls.editor.config.target.targets) == 3

    controls.spn_target_count.setValue(2)
    QApplication.processEvents()
    assert not controls._has_violations()
    assert controls.editor.config.target.count == 2
    assert len(controls.editor.config.target.targets) == 2


# ───────────────────────────────────────────────────────────────────
# 5.  Motion parameter pages
# ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", ["line", "circle", "figure8", "random"])
def test_motion_page(controls, kind: str) -> None:  # noqa: ANN001
    """Each motion kind must display its parameter page without errors."""
    controls.cmb_tgt_motion.setCurrentText(kind)
    QApplication.processEvents()
    assert not controls._has_violations(), f"Motion kind {kind} caused violations"
    assert controls.motion_stack.current_kind() == kind


# ───────────────────────────────────────────────────────────────────
# 6.  MP4: invalid path keeps Start disabled, valid clip enables it
# ───────────────────────────────────────────────────────────────────

def test_mp4_invalid_path_disables_start(controls) -> None:  # noqa: ANN001
    """An invalid MP4 path must keep Start disabled."""
    controls.cmb_input.setCurrentText("MP4 Video")
    QApplication.processEvents()

    # Probe a non-existent file
    controls._probe_mp4("/nonexistent/fake_video.mp4")
    QApplication.processEvents()
    assert not controls.btn_start.isEnabled(), "Start should be disabled with invalid MP4"


def test_mp4_valid_clip_enables_start(controls, tmp_path) -> None:  # noqa: ANN001
    """A valid MP4 generated by gen_test_video.py must enable Start."""
    try:
        from scripts.gen_test_video import generate_test_video
    except ImportError:
        pytest.skip("gen_test_video not importable or cv2 missing")

    video_path = tmp_path / "test_clip.mp4"
    try:
        generate_test_video(out_path=str(video_path), seconds=0.5, seed=42, fps=30.0)
    except Exception as e:
        pytest.skip(f"Cannot generate test video: {e}")

    controls.cmb_input.setCurrentText("MP4 Video")
    QApplication.processEvents()

    controls.mp4_section.set_path(str(video_path))
    controls._probe_mp4(str(video_path))
    controls._apply_dict({"input.mp4_path": str(video_path)})
    QApplication.processEvents()

    assert controls.btn_start.isEnabled(), "Start should be enabled with valid MP4"


# ───────────────────────────────────────────────────────────────────
# 7.  Config save/load round trip
# ───────────────────────────────────────────────────────────────────

def test_save_load_round_trip(controls, tmp_path) -> None:  # noqa: ANN001
    """Saving and loading config must produce an identical to_dict."""
    # Modify some settings
    controls.spn_fps.setValue(60.0)
    controls.spn_slew.setValue(7.0)
    controls.spn_seed.setValue(123)
    QApplication.processEvents()

    original = to_dict(controls.editor.config)

    # Save
    save_path = tmp_path / "config.json"
    json_str = to_json(controls.editor.config)
    save_path.write_text(json_str, encoding="utf-8")

    # Load into a fresh editor
    loaded_cfg = from_json(save_path.read_text(encoding="utf-8"))
    loaded = to_dict(loaded_cfg)

    assert original == loaded, "Round-trip save/load produced different config"


# ───────────────────────────────────────────────────────────────────
# 8.  CLI: skylock gui --config bad.json → exit 2
# ───────────────────────────────────────────────────────────────────

def test_cli_gui_bad_config_exits_2(tmp_path) -> None:
    """``skylock gui --config bad.json`` must exit 2 without opening a window."""
    bad_config = tmp_path / "bad.json"
    bad_config.write_text('{"camera": {"fps": -1}}', encoding="utf-8")

    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    result = subprocess.run(
        [sys.executable, "-m", "skylock", "gui", "--config", str(bad_config)],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )

    assert result.returncode == 2, (
        f"Expected exit code 2, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ───────────────────────────────────────────────────────────────────
# 9.  Start button :disabled style present
# ───────────────────────────────────────────────────────────────────

def test_start_button_has_disabled_style(controls) -> None:  # noqa: ANN001
    """btn_start stylesheet must contain a :disabled rule."""
    ss = controls.btn_start.styleSheet()
    assert ":disabled" in ss


# ───────────────────────────────────────────────────────────────────
# 10. Manual rate property
# ───────────────────────────────────────────────────────────────────

def test_manual_rate_property(controls) -> None:  # noqa: ANN001
    """manual_rate_deg_s property must reflect the spin box value."""
    controls.spn_manual_rate.setValue(3.5)
    assert controls.manual_rate_deg_s == pytest.approx(3.5)


# ───────────────────────────────────────────────────────────────────
# 11. Atmosphere section
# ───────────────────────────────────────────────────────────────────

def test_atmosphere_strength_range(controls) -> None:  # noqa: ANN001
    """Atmosphere strength at 0 and 1 must not produce errors."""
    controls.atmos_section.cmb_mode.setCurrentText("Haze")
    QApplication.processEvents()

    controls.atmos_section.spn_strength.setValue(0.0)
    QApplication.processEvents()
    assert not controls._has_violations()

    controls.atmos_section.spn_strength.setValue(1.0)
    QApplication.processEvents()
    assert not controls._has_violations()
