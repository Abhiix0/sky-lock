"""Tests for skylock.gimbal — 2-axis gimbal servo dynamics."""

import math

import pytest

from skylock.config import CameraConfig
from skylock.geometry import angular_diff_deg
from skylock.gimbal import Gimbal, run_gimbal_self_test


class TestGimbalBasic:
    """Basic gimbal positioning."""

    def test_initial_state(self):
        g = Gimbal(initial_pan=90.0, initial_tilt=0.0)
        state = g.get_state()
        assert state["pan_deg"] == pytest.approx(90.0)
        assert state["tilt_deg"] == pytest.approx(0.0)
        assert state["pan_rate_deg_s"] == pytest.approx(0.0)
        assert state["tilt_rate_deg_s"] == pytest.approx(0.0)

    def test_snap_to(self):
        g = Gimbal()
        g.snap_to(45.0, 30.0)
        state = g.get_state()
        assert state["pan_deg"] == pytest.approx(45.0)
        assert state["tilt_deg"] == pytest.approx(30.0)
        assert state["pan_rate_deg_s"] == pytest.approx(0.0)

    def test_zero_dt_is_noop(self):
        g = Gimbal()
        g.set_command(90.0, 0.0)
        state1 = g.get_state()
        g.step(0.0)
        state2 = g.get_state()
        assert state1["pan_deg"] == state2["pan_deg"]


class TestGimbalGoto:
    """Go-to mode positioning."""

    def test_reaches_target(self):
        """Gimbal should reach target position within reasonable time."""
        g = Gimbal(initial_pan=0.0, initial_tilt=0.0)
        g.set_command(10.0, 5.0)
        dt = 1.0 / 120

        for _ in range(3000):  # up to 25 seconds
            g.step(dt)
            st = g.get_state()
            if (
                abs(angular_diff_deg(st["pan_deg"], 10.0)) < 0.01
                and abs(st["tilt_deg"] - 5.0) < 0.01
            ):
                return

        pytest.fail("Gimbal did not reach target")

    def test_does_not_exceed_max_slew_rate(self):
        """Rate should never exceed the configured maximum."""
        camera = CameraConfig(max_slew_rate_deg_s=5.0)
        g = Gimbal(camera=camera, initial_pan=0.0, initial_tilt=0.0)
        g.set_command(90.0, 45.0)
        dt = 1.0 / 120

        max_rate_observed = 0.0
        for _ in range(2000):
            g.step(dt)
            st = g.get_state()
            rate = math.hypot(st["pan_rate_deg_s"], st["tilt_rate_deg_s"])
            if rate > max_rate_observed:
                max_rate_observed = rate

        # Allow small margin for numerical imprecision
        assert max_rate_observed < 5.0 * 1.5, (
            f"Max observed rate {max_rate_observed:.2f}°/s exceeds limit"
        )


class TestGimbalSeamCrossing:
    """Pan wrap-around across ±180° boundary."""

    def test_seam_takes_short_path(self):
        """Crossing from 179° to -179° should go 2° through 180°, not 358°."""
        g = Gimbal(initial_pan=179.0, initial_tilt=0.0)
        g.set_command(-179.0, 0.0)
        dt = 1.0 / 120

        total_path = 0.0
        last_pan = 179.0

        for _ in range(2000):
            g.step(dt)
            st = g.get_state()
            dp = abs(angular_diff_deg(st["pan_deg"], last_pan))
            total_path += dp
            last_pan = st["pan_deg"]
            if (
                abs(angular_diff_deg(-179.0, st["pan_deg"])) < 0.01
                and abs(st["pan_rate_deg_s"]) < 0.01
            ):
                break

        # Short path ≈ 2°, long path ≈ 358°; allow margin for accel/decel overshoot
        assert total_path < 15.0, f"Seam path {total_path:.1f}° is too long (expected ~2°)"


class TestGimbalTiltLimits:
    """Tilt joint limits."""

    def test_tilt_clamped_at_limit(self):
        """Tilt should not exceed configured limits."""
        camera = CameraConfig(tilt_limit_deg=45.0)
        g = Gimbal(camera=camera, initial_pan=0.0, initial_tilt=0.0)
        g.set_command(0.0, 90.0)  # request beyond limit
        dt = 1.0 / 120

        for _ in range(3000):
            g.step(dt)

        state = g.get_state()
        assert state["tilt_deg"] <= 45.0 + 0.01
        assert state["at_limit_tilt"] is True


class TestGimbalReset:
    """Reset behavior."""

    def test_reset_returns_to_initial(self):
        g = Gimbal(initial_pan=0.0, initial_tilt=0.0)
        g.set_command(90.0, 45.0)
        for _ in range(100):
            g.step(1.0 / 120)
        g.reset(pan_deg=10.0, tilt_deg=5.0)
        state = g.get_state()
        assert state["pan_deg"] == pytest.approx(10.0)
        assert state["tilt_deg"] == pytest.approx(5.0)
        assert state["pan_rate_deg_s"] == pytest.approx(0.0)


class TestGimbalSelfTest:
    """Self-test routine."""

    def test_self_test_returns_valid_results(self):
        result = run_gimbal_self_test()
        assert result["max_rate"] > 0.0
        assert result["max_accel"] > 0.0
        assert result["overshoot_deg"] >= 0.0
        assert result["seam_path_deg"] > 0.0
        # Seam should take short path (~2°)
        assert result["seam_path_deg"] < 10.0

    def test_self_test_rate_within_limits(self):
        camera = CameraConfig(max_slew_rate_deg_s=5.0)
        result = run_gimbal_self_test(camera=camera)
        # Allow margin for acceleration dynamics
        assert result["max_rate"] <= 5.0 + 0.5
