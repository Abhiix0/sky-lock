"""Tests that document known bugs (a)–(f) in ControlsPanel config binding.

Bug IDs follow the Phase G0 spec:
  G-0A  invalid disturbance key "disturbances.jitter.enabled" /
              "disturbances.atmosphere.kind" → ConfigError
  G-0B  figure8 motion sends unknown field "extent_deg"
  G-0C  shape combo contains "rect" (invalid)
  G-0D  slew_rate 3.0 fails cross-field validation against scan_rate
  G-0E  enabling a disturbance checkbox leaves magnitude at 0.0 → no effect
  G-0F  "Low light" atmosphere option is absent from the combo

All bugs were fixed in G1.  Tests verify they stay fixed.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.gui


# ---------------------------------------------------------------------------
# G-0E: enabling disturbance checkboxes — magnitude stays 0.0
# ---------------------------------------------------------------------------

def test_gaussian_checkbox_enables_valid_config(controls) -> None:  # noqa: ANN001
    """Ticking Gaussian noise must produce enabled=True AND sigma_levels > 0."""
    controls.dist_gaussian.chk.setChecked(True)

    assert not controls._has_violations(), (
        f"Unexpected config error"
    )
    assert controls.editor.config.disturbances.gaussian.enabled is True
    assert controls.editor.config.disturbances.gaussian.sigma_levels > 0, (
        "sigma_levels must be > 0 when Gaussian noise is enabled"
    )


def test_salt_pepper_checkbox_enables_valid_config(controls) -> None:  # noqa: ANN001
    """Ticking Salt & Pepper must produce enabled=True AND density > 0."""
    controls.dist_salt_pepper.chk.setChecked(True)

    assert not controls._has_violations()
    assert controls.editor.config.disturbances.salt_pepper.enabled is True
    assert controls.editor.config.disturbances.salt_pepper.density > 0, (
        "density must be > 0 when S&P noise is enabled"
    )


def test_jitter_checkbox_enables_valid_config(controls) -> None:  # noqa: ANN001
    """Ticking camera jitter must succeed and set max_px_frame > 0."""
    controls.dist_jitter.chk.setChecked(True)

    assert not controls._has_violations()
    assert controls.editor.config.disturbances.camera_jitter.enabled is True
    assert controls.editor.config.disturbances.camera_jitter.max_px_frame > 0, (
        "max_px_frame must be > 0 when jitter is enabled"
    )


def test_drift_checkbox_enables_valid_config(controls) -> None:  # noqa: ANN001
    """Ticking platform drift must succeed and set max_px_frame > 0."""
    controls.dist_drift.chk.setChecked(True)

    assert not controls._has_violations()
    assert controls.editor.config.disturbances.platform.enabled is True
    assert controls.editor.config.disturbances.platform.max_px_frame > 0, (
        "max_px_frame must be > 0 when platform drift is enabled"
    )


def test_blur_checkbox_enables_valid_config(controls) -> None:  # noqa: ANN001
    """Ticking optical blur must produce enabled=True AND sigma_px > 0."""
    controls.dist_blur.chk.setChecked(True)

    assert not controls._has_violations()
    assert controls.editor.config.disturbances.blur.enabled is True
    assert controls.editor.config.disturbances.blur.sigma_px > 0, (
        "sigma_px must be > 0 when blur is enabled"
    )


# ---------------------------------------------------------------------------
# G-0A: atmosphere uses invalid key "disturbances.atmosphere.kind"
# (real key is "disturbances.atmosphere.mode")
# ---------------------------------------------------------------------------

def test_atmosphere_combo_change_no_error(controls) -> None:  # noqa: ANN001
    """Changing the atmosphere combo to Haze must not show a config error."""
    controls.atmos_section.cmb_mode.setCurrentText("Haze")

    assert not controls._has_violations()
    assert controls.editor.config.disturbances.atmosphere.mode == "haze"


# ---------------------------------------------------------------------------
# G-0F: "Low light" option absent from atmosphere combo
# ---------------------------------------------------------------------------

def test_atmosphere_options_complete(controls) -> None:  # noqa: ANN001
    """Atmosphere combo must include all five PS_SPEC modes including low_light."""
    cmb = controls.atmos_section.cmb_mode
    items_normalised = {
        cmb.itemText(i).lower().replace(" ", "_")
        for i in range(cmb.count())
    }
    expected = {"clear", "haze", "fog", "rain", "low_light"}
    assert items_normalised == expected, (
        f"Missing atmosphere options: {expected - items_normalised}"
    )


# ---------------------------------------------------------------------------
# G-0B: figure8 sends unknown field "extent_deg"
# ---------------------------------------------------------------------------

def test_figure8_valid(controls) -> None:  # noqa: ANN001
    """Selecting figure8 motion must not produce a config error."""
    controls.cmb_tgt_motion.setCurrentText("figure8")

    assert not controls._has_violations()
    t0 = controls.editor.config.target.targets[0]
    assert t0.motion.kind == "figure8"


# ---------------------------------------------------------------------------
# G-0C: "rect" is not a valid shape
# ---------------------------------------------------------------------------

def test_all_shape_options_valid(controls) -> None:  # noqa: ANN001
    """Every item in the shape combo must be a valid TargetConfig shape."""
    errors = []
    for i in range(controls.cmb_tgt_shape.count()):
        controls.cmb_tgt_shape.setCurrentIndex(i)
        if controls._has_violations():
            errors.append(
                f"shape '{controls.cmb_tgt_shape.currentText()}': violation"
            )
    assert not errors, "Invalid shape(s) in combo:\n" + "\n".join(errors)


# ---------------------------------------------------------------------------
# G-0D: slew_rate 3.0 fails cross-field validation (scan_rate default 5.0 > 3.0)
# ---------------------------------------------------------------------------

def test_slew_3_is_valid(controls) -> None:  # noqa: ANN001
    """Setting slew rate to 3.0 deg/s must not show a config error."""
    controls.spn_slew.setValue(3.0)

    assert not controls._has_violations()
    assert controls.editor.config.gimbal.slew_rate_deg_s == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# G-07 (visual): disabled Start button must have a :disabled style rule
# ---------------------------------------------------------------------------

def test_start_button_disabled_looks_disabled(controls) -> None:  # noqa: ANN001
    """The Start button stylesheet must contain a :disabled rule."""
    ss = controls.btn_start.styleSheet()
    assert ":disabled" in ss, (
        f"btn_start styleSheet has no ':disabled' rule.\n"
        f"Current styleSheet: {ss!r}"
    )
