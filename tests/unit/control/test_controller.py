"""Unit tests for PointingController modes, deadband, manual override, and firewall."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from skylock.config.models import CameraConfig, ControlConfig
from skylock.control.controller import PointingController
from skylock.core.enums import ControlIntentMode, ControlMode
from skylock.core.types import ControlIntent, Pointing, TargetEstimate


def _make_controller(
    mode: ControlMode = ControlMode.AUTO,
    deadband_px: float = 0.5,
    max_slew: float = 10.0,
) -> PointingController:
    control_cfg = ControlConfig(
        kp=4.0,
        ki=0.5,
        kd=0.2,
        kff=1.0,
        d_filter_alpha=0.8,
        integral_clamp=2.0,
        deadband_px=deadband_px,
        mode=mode,
    )
    camera_cfg = CameraConfig(
        width=640,
        height=480,
        fov_h_deg=4.0,
        fov_v_deg=3.0,
        fps=30.0,
    )
    return PointingController(control_cfg, camera_cfg, max_slew_rate_deg_s=max_slew)


def test_hold_mode_returns_zeros() -> None:
    """HOLD intent produces zero rate command."""
    ctrl = _make_controller()
    intent = ControlIntent(mode=ControlIntentMode.HOLD)
    cmd = ctrl.step(intent=intent, estimate=None, pointing=Pointing(0.0, 0.0), dt=1.0 / 30.0)
    assert cmd.pan_rate_deg_s == 0.0
    assert cmd.tilt_rate_deg_s == 0.0


def test_goto_convergence() -> None:
    """GOTO intent slews proportionally towards setpoint and stops upon arrival."""
    ctrl = _make_controller(max_slew=5.0)
    dt = 1.0 / 30.0
    current_pointing = Pointing(pan_deg=0.0, tilt_deg=0.0)
    intent = ControlIntent(
        mode=ControlIntentMode.GOTO,
        setpoint_pan_deg=10.0,
        setpoint_tilt_deg=-5.0,
    )

    # Initial command should slew at max rate towards setpoint
    cmd_init = ctrl.step(intent=intent, estimate=None, pointing=current_pointing, dt=dt)
    assert cmd_init.pan_rate_deg_s > 0.0
    assert cmd_init.tilt_rate_deg_s < 0.0
    assert abs(cmd_init.pan_rate_deg_s) <= 5.0
    assert abs(cmd_init.tilt_rate_deg_s) <= 5.0

    # Simulate convergence
    pointing = Pointing(0.0, 0.0)
    for _ in range(120):
        cmd = ctrl.step(intent=intent, estimate=None, pointing=pointing, dt=dt)
        pointing = Pointing(
            pan_deg=pointing.pan_deg + cmd.pan_rate_deg_s * dt,
            tilt_deg=pointing.tilt_deg + cmd.tilt_rate_deg_s * dt,
        )

    assert pointing.pan_deg == pytest.approx(10.0, abs=0.1)
    assert pointing.tilt_deg == pytest.approx(-5.0, abs=0.1)


def test_track_mode_and_feedforward() -> None:
    """TRACK mode computes PID rate from image error and adds velocity feedforward."""
    ctrl = _make_controller(max_slew=10.0)
    dt = 1.0 / 30.0

    # Image error: target is +100 px to the right (requires positive pan)
    # Target estimate has +1.5 deg/s pan angular velocity
    intent = ControlIntent(
        mode=ControlIntentMode.TRACK,
        image_error_px=(100.0, 0.0),
    )
    estimate = TargetEstimate(
        pan_deg=0.0,
        tilt_deg=0.0,
        pan_rate=1.5,
        tilt_rate=0.0,
        px=420.0,
        py=240.0,
        sigma_deg=0.01,
        from_measurement=True,
    )

    cmd = ctrl.step(
        intent=intent,
        estimate=estimate,
        pointing=Pointing(0.0, 0.0),
        dt=dt,
    )

    # IFOV_h = 4.0 / 640 = 0.00625 deg/px. Error = 100 * 0.00625 = 0.625 deg
    # Kp = 4.0 -> P-term = 2.5 deg/s. Feedforward = 1.0 * 1.5 = 1.5 deg/s
    # Expected pan rate approx 4.0 deg/s
    assert cmd.pan_rate_deg_s > 3.5
    assert cmd.tilt_rate_deg_s == pytest.approx(0.0, abs=1e-3)


def test_deadband_suppresses_small_errors() -> None:
    """Pixel errors within deadband_px are treated as zero."""
    ctrl = _make_controller(deadband_px=2.0)
    dt = 1.0 / 30.0

    # Sub-deadband error: hypot(1.0, 1.0) = 1.414 < 2.0 px
    intent = ControlIntent(
        mode=ControlIntentMode.TRACK,
        image_error_px=(1.0, 1.0),
    )
    cmd = ctrl.step(intent=intent, estimate=None, pointing=Pointing(0.0, 0.0), dt=dt)
    assert cmd.pan_rate_deg_s == pytest.approx(0.0)
    assert cmd.tilt_rate_deg_s == pytest.approx(0.0)

    # Above deadband: hypot(3.0, 0.0) = 3.0 > 2.0 px
    intent_large = ControlIntent(
        mode=ControlIntentMode.TRACK,
        image_error_px=(3.0, 0.0),
    )
    cmd_large = ctrl.step(intent=intent_large, estimate=None, pointing=Pointing(0.0, 0.0), dt=dt)
    assert cmd_large.pan_rate_deg_s > 0.0


def test_manual_mode_override() -> None:
    """In MANUAL mode, controller returns externally set rates and ignores tracking intent."""
    ctrl = _make_controller(mode=ControlMode.MANUAL)
    ctrl.set_manual_rate(pan_rate_deg_s=3.5, tilt_rate_deg_s=-2.0)

    # Even with a huge TRACK intent
    intent = ControlIntent(
        mode=ControlIntentMode.TRACK,
        image_error_px=(-200.0, 150.0),
    )
    cmd = ctrl.step(intent=intent, estimate=None, pointing=Pointing(0.0, 0.0), dt=1.0 / 30.0)

    assert cmd.pan_rate_deg_s == pytest.approx(3.5)
    assert cmd.tilt_rate_deg_s == pytest.approx(-2.0)


def test_ground_truth_isolation_signature_and_ast() -> None:
    """PointingController must strictly not import, annotate, or reference GroundTruthSample."""
    # 1. Inspect function signatures and type annotations
    methods_to_check = [
        PointingController.__init__,
        PointingController.step,
        PointingController.reset,
        PointingController.set_manual_rate,
    ]
    for method in methods_to_check:
        sig = inspect.signature(method)
        for param in sig.parameters.values():
            param_str = str(param.annotation)
            assert "GroundTruthSample" not in param_str
            assert "simulation" not in param_str
        ret_str = str(sig.return_annotation)
        assert "GroundTruthSample" not in ret_str
        assert "simulation" not in ret_str

    # 2. AST scan of entire control package
    control_dir = Path(__file__).resolve().parents[3] / "src" / "skylock" / "control"
    for py_file in control_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert node.id != "GroundTruthSample", (
                    f"GroundTruthSample identifier found in {py_file}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "simulation" not in alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert "simulation" not in node.module
