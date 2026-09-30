"""Tests for skylock.controller — PID controller with feed-forward."""

import pytest

from skylock.config import CameraConfig, ControllerConfig
from skylock.controller import Controller


class TestControllerBasic:
    """Basic controller behavior."""

    def test_zero_dt_returns_zeros(self):
        ctrl = Controller()
        result = ctrl.step(0.0, 0.0, 0.0, 0.0, 0.0)
        assert result["pan_rate_deg_s"] == 0.0
        assert result["tilt_rate_deg_s"] == 0.0

    def test_zero_error_produces_near_zero_output(self):
        ctrl = Controller()
        result = ctrl.step(1.0 / 30, 45.0, 10.0, 45.0, 10.0)
        assert abs(result["pan_rate_deg_s"]) < 0.1
        assert abs(result["tilt_rate_deg_s"]) < 0.1
        assert result["pan_err_deg"] == pytest.approx(0.0, abs=0.01)

    def test_positive_error_produces_positive_rate(self):
        ctrl = Controller()
        result = ctrl.step(1.0 / 30, 0.0, 0.0, 5.0, 3.0)
        assert result["pan_rate_deg_s"] > 0.0
        assert result["tilt_rate_deg_s"] > 0.0


class TestControllerAntiWindup:
    """Anti-windup and saturation behavior."""

    def test_rate_clamped_to_max_slew(self):
        """Output should not exceed max slew rate."""
        camera = CameraConfig(max_slew_rate_deg_s=5.0)
        ctrl = Controller(camera=camera)
        # Large error to saturate
        result = ctrl.step(1.0 / 30, 0.0, 0.0, 90.0, 45.0)
        assert abs(result["pan_rate_deg_s"]) <= 5.0 + 1e-9
        assert abs(result["tilt_rate_deg_s"]) <= 5.0 + 1e-9

    def test_custom_max_slew_override(self):
        """max_slew_rate parameter should override camera config."""
        ctrl = Controller()
        result = ctrl.step(
            1.0 / 30,
            0.0,
            0.0,
            90.0,
            45.0,
            max_slew_rate=2.0,
        )
        assert abs(result["pan_rate_deg_s"]) <= 2.0 + 1e-9
        assert abs(result["tilt_rate_deg_s"]) <= 2.0 + 1e-9


class TestControllerFeedForward:
    """Feed-forward velocity compensation."""

    def test_feed_forward_reduces_steady_state_error(self):
        """With feed-forward ON, tracking a ramp should have lower SS error."""
        camera = CameraConfig(max_slew_rate_deg_s=10.0)

        # Controller with feed-forward ON
        ctrl_ff = Controller(
            config=ControllerConfig(kff=1.0),
            camera=camera,
        )
        # Controller with feed-forward OFF
        ctrl_no_ff = Controller(
            config=ControllerConfig(kff=0.0),
            camera=camera,
        )

        dt = 1.0 / 30
        ramp_rate = 2.0  # deg/s
        gimbal_pan = 0.0
        gimbal_pan_no_ff = 0.0

        # Run for 3 seconds
        for step_i in range(90):
            t = step_i * dt
            target_pan = ramp_rate * t

            # With FF
            res_ff = ctrl_ff.step(
                dt,
                gimbal_pan,
                0.0,
                target_pan,
                0.0,
                los_pan_rate_deg_s=ramp_rate,
            )
            gimbal_pan += res_ff["pan_rate_deg_s"] * dt

            # Without FF
            res_no_ff = ctrl_no_ff.step(
                dt,
                gimbal_pan_no_ff,
                0.0,
                target_pan,
                0.0,
            )
            gimbal_pan_no_ff += res_no_ff["pan_rate_deg_s"] * dt

        # Final errors
        final_target = ramp_rate * 90 * dt
        err_ff = abs(final_target - gimbal_pan)
        err_no_ff = abs(final_target - gimbal_pan_no_ff)

        assert err_ff < err_no_ff, (
            f"FF error ({err_ff:.4f}°) should be less than no-FF error ({err_no_ff:.4f}°)"
        )
        # With FF, SS error should be very small
        assert err_ff < 0.5


class TestControllerReset:
    """Reset behavior."""

    def test_reset_clears_state(self):
        ctrl = Controller()
        # Run a few steps
        for _ in range(10):
            ctrl.step(1.0 / 30, 0.0, 0.0, 10.0, 5.0)
        ctrl.reset()
        # After reset, first step should behave like fresh controller
        result = ctrl.step(1.0 / 30, 0.0, 0.0, 0.0, 0.0)
        assert abs(result["pan_rate_deg_s"]) < 0.1
