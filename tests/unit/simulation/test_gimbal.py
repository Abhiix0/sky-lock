"""Unit tests for VirtualGimbal physical actuator dynamics and constraints."""

from __future__ import annotations

import numpy as np
import pytest

from skylock.config.models import GimbalConfig
from skylock.core.types import ControlCommand
from skylock.simulation.gimbal import VirtualGimbal


def test_initial_state() -> None:
    """VirtualGimbal initializes at configured initial angles with zero velocities."""
    cfg = GimbalConfig(
        initial=(5.0, -3.0),
        slew_rate_deg_s=5.0,
        accel_deg_s2=60.0,
    )
    g = VirtualGimbal(cfg)
    p = g.pointing
    assert p.pan_deg == pytest.approx(5.0)
    assert p.tilt_deg == pytest.approx(-3.0)
    assert g.pan_rate_deg_s == pytest.approx(0.0)
    assert g.tilt_rate_deg_s == pytest.approx(0.0)
    assert not g.at_limit


def test_velocity_and_accel_limits_property_test() -> None:
    """VirtualGimbal strictly enforces velocity and acceleration limits under random commands."""
    slew = 6.0
    accel = 50.0
    dt = 1.0 / 30.0
    cfg = GimbalConfig(
        slew_rate_deg_s=slew,
        max_slew_rate_deg_s=10.0,
        accel_deg_s2=accel,
        initial=(0.0, 0.0),
        substeps=4,
        # Use wide limits to avoid hitting them during the test
        pan_limit_deg=(-180.0, 180.0),
        tilt_limit_deg=(-90.0, 90.0),
    )
    g = VirtualGimbal(cfg)
    rng = np.random.default_rng(12345)

    prev_pan_rate = 0.0
    prev_tilt_rate = 0.0

    for _ in range(500):
        # Generate extreme random rate commands
        cmd = ControlCommand(
            pan_rate_deg_s=float(rng.uniform(-25.0, 25.0)),
            tilt_rate_deg_s=float(rng.uniform(-25.0, 25.0)),
        )
        g.command(cmd, dt)

        # 1. Velocity magnitude must never exceed effective max slew
        assert abs(g.pan_rate_deg_s) <= slew + 1e-9
        assert abs(g.tilt_rate_deg_s) <= slew + 1e-9

        # 2. Acceleration must never exceed configured limit
        d_pan_rate = abs(g.pan_rate_deg_s - prev_pan_rate) / dt
        d_tilt_rate = abs(g.tilt_rate_deg_s - prev_tilt_rate) / dt
        # Allow tiny epsilon for numerical float precision
        assert d_pan_rate <= accel + 1e-3, f"Pan accel {d_pan_rate} exceeds limit {accel}"
        assert d_tilt_rate <= accel + 1e-3, f"Tilt accel {d_tilt_rate} exceeds limit {accel}"

        prev_pan_rate = g.pan_rate_deg_s
        prev_tilt_rate = g.tilt_rate_deg_s


def test_no_snap_guarantee() -> None:
    """Gimbal pointing can NEVER snap; change per frame is bounded by slew * dt + eps."""
    slew = 8.0
    accel = 100.0
    dt = 1.0 / 30.0
    cfg = GimbalConfig(
        slew_rate_deg_s=slew,
        accel_deg_s2=accel,
        initial=(0.0, 0.0),
        substeps=4,
    )
    g = VirtualGimbal(cfg)

    # Even with an outrageous command of 500 deg/s
    cmd = ControlCommand(pan_rate_deg_s=500.0, tilt_rate_deg_s=-500.0)

    for _ in range(120):
        prev_pointing = g.pointing
        g.command(cmd, dt)
        new_pointing = g.pointing

        d_pan = abs(new_pointing.pan_deg - prev_pointing.pan_deg)
        d_tilt = abs(new_pointing.tilt_deg - prev_pointing.tilt_deg)

        # Max displacement in dt is slew * dt + eps
        max_d = slew * dt + 1e-7
        assert d_pan <= max_d, f"Pan displacement {d_pan} snapped beyond {max_d}"
        assert d_tilt <= max_d, f"Tilt displacement {d_tilt} snapped beyond {max_d}"


def test_joint_limits_clamping_and_flags() -> None:
    """Joint limits clamp position, set at_limit flags, and zero outward velocity."""
    cfg = GimbalConfig(
        slew_rate_deg_s=10.0,
        pan_limit_deg=(-20.0, 20.0),
        tilt_limit_deg=(-15.0, 15.0),
        accel_deg_s2=120.0,
        initial=(0.0, 0.0),
    )
    g = VirtualGimbal(cfg)
    dt = 1.0 / 30.0

    # Drive hard in positive direction
    cmd = ControlCommand(pan_rate_deg_s=10.0, tilt_rate_deg_s=10.0)
    for _ in range(120):
        g.command(cmd, dt)

    assert g.pointing.pan_deg == pytest.approx(20.0, abs=1e-6)
    assert g.pointing.tilt_deg == pytest.approx(15.0, abs=1e-6)
    assert g.at_limit_pan
    assert g.at_limit_tilt
    assert g.at_limit
    assert g.pan_rate_deg_s == pytest.approx(0.0)
    assert g.tilt_rate_deg_s == pytest.approx(0.0)

    # Now command back inward (negative rate) - should disengage limit
    cmd_reverse = ControlCommand(pan_rate_deg_s=-5.0, tilt_rate_deg_s=-5.0)
    g.command(cmd_reverse, dt)
    assert g.pointing.pan_deg < 20.0
    assert g.pointing.tilt_deg < 15.0
    assert not g.at_limit_pan
    assert not g.at_limit_tilt


def test_goto_position_mode() -> None:
    """Position command mode smoothly slews towards target angle and decelerates to a stop."""
    cfg = GimbalConfig(
        slew_rate_deg_s=5.0,
        accel_deg_s2=50.0,
        initial=(0.0, 0.0),
        # Use wide limits to allow reaching the commanded position
        pan_limit_deg=(-180.0, 180.0),
        tilt_limit_deg=(-90.0, 90.0),
    )
    g = VirtualGimbal(cfg)
    dt = 1.0 / 60.0

    for _ in range(300):
        g.command_position(pan_deg=10.0, tilt_deg=-5.0, dt=dt)
        if (
            abs(g.pointing.pan_deg - 10.0) < 1e-3
            and abs(g.pointing.tilt_deg - (-5.0)) < 1e-3
            and abs(g.pan_rate_deg_s) < 1e-3
        ):
            break

    assert g.pointing.pan_deg == pytest.approx(10.0, abs=1e-2)
    assert g.pointing.tilt_deg == pytest.approx(-5.0, abs=1e-2)
    assert abs(g.pan_rate_deg_s) < 1e-2


def test_reset_behavior() -> None:
    """Reset restores initial pointing, zero velocities, and clears limits."""
    cfg = GimbalConfig(
        slew_rate_deg_s=5.0,
        initial=(2.0, -1.0),
    )
    g = VirtualGimbal(cfg)
    dt = 1.0 / 30.0

    # Move gimbal
    g.command(ControlCommand(pan_rate_deg_s=5.0, tilt_rate_deg_s=5.0), dt * 30)
    assert g.pointing.pan_deg > 2.0

    # Reset
    g.reset()
    assert g.pointing.pan_deg == pytest.approx(2.0)
    assert g.pointing.tilt_deg == pytest.approx(-1.0)
    assert g.pan_rate_deg_s == pytest.approx(0.0)
    assert g.tilt_rate_deg_s == pytest.approx(0.0)
    assert not g.at_limit
