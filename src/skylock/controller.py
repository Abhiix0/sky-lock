"""
PID controller with feed-forward and anti-windup for line-of-sight tracking.

Commands angular rates (deg/s) to the gimbal servo based on the error
between the estimated target LOS and the current gimbal angles.

JS reference: src/tracking/controller.js
"""

from __future__ import annotations

from skylock.config import CAMERA, CONTROLLER, CameraConfig, ControllerConfig
from skylock.geometry import angular_diff_deg


class Controller:
    """Line-of-sight tracking PID controller with feed-forward and anti-windup.

    Args:
        config: Controller tuning parameters.
        camera: Camera config for slew rate limits.
    """

    def __init__(
        self,
        config: ControllerConfig = CONTROLLER,
        camera: CameraConfig = CAMERA,
    ) -> None:
        self._cfg = config
        self._camera = camera

        self._int_pan: float = 0.0
        self._int_tilt: float = 0.0
        self._prev_pan_err: float = 0.0
        self._prev_tilt_err: float = 0.0
        self._filt_deriv_pan: float = 0.0
        self._filt_deriv_tilt: float = 0.0
        self._has_prev: bool = False

    def reset(self) -> None:
        """Reset integrator and filter states."""
        self._int_pan = 0.0
        self._int_tilt = 0.0
        self._prev_pan_err = 0.0
        self._prev_tilt_err = 0.0
        self._filt_deriv_pan = 0.0
        self._filt_deriv_tilt = 0.0
        self._has_prev = False

    def step(
        self,
        dt: float,
        gimbal_pan_deg: float,
        gimbal_tilt_deg: float,
        los_pan_deg: float,
        los_tilt_deg: float,
        los_pan_rate_deg_s: float = 0.0,
        los_tilt_rate_deg_s: float = 0.0,
        max_slew_rate: float | None = None,
    ) -> dict[str, float]:
        """Advance controller by one timestep.

        Args:
            dt: Timestep in seconds (must be > 0).
            gimbal_pan_deg: Current gimbal pan angle in degrees.
            gimbal_tilt_deg: Current gimbal tilt angle in degrees.
            los_pan_deg: Target LOS pan angle in degrees.
            los_tilt_deg: Target LOS tilt angle in degrees.
            los_pan_rate_deg_s: Target LOS pan rate in deg/s (for feed-forward).
            los_tilt_rate_deg_s: Target LOS tilt rate in deg/s (for feed-forward).
            max_slew_rate: Optional slew velocity limit override in deg/s.

        Returns:
            Dict with pan_rate_deg_s, tilt_rate_deg_s, pan_err_deg, tilt_err_deg.
        """
        if dt <= 0.0:
            return {
                "pan_rate_deg_s": 0.0,
                "tilt_rate_deg_s": 0.0,
                "pan_err_deg": 0.0,
                "tilt_err_deg": 0.0,
            }

        vmax = max_slew_rate if max_slew_rate is not None else self._camera.max_slew_rate_deg_s

        kp = self._cfg.kp
        ki = self._cfg.ki
        kd = self._cfg.kd
        kff = self._cfg.kff
        alpha = self._cfg.d_filter_alpha
        max_int = self._cfg.integral_clamp_deg_s / max(ki, 1e-4)

        # Shortest angular difference
        pan_err = angular_diff_deg(los_pan_deg, gimbal_pan_deg)
        tilt_err = los_tilt_deg - gimbal_tilt_deg

        # Filtered derivative
        if not self._has_prev:
            self._prev_pan_err = pan_err
            self._prev_tilt_err = tilt_err
            self._filt_deriv_pan = 0.0
            self._filt_deriv_tilt = 0.0
            self._has_prev = True

        raw_d_pan = (pan_err - self._prev_pan_err) / dt
        raw_d_tilt = (tilt_err - self._prev_tilt_err) / dt

        self._filt_deriv_pan = alpha * raw_d_pan + (1.0 - alpha) * self._filt_deriv_pan
        self._filt_deriv_tilt = alpha * raw_d_tilt + (1.0 - alpha) * self._filt_deriv_tilt

        self._prev_pan_err = pan_err
        self._prev_tilt_err = tilt_err

        # Anti-windup conditional integration
        tent_int_pan = max(-max_int, min(max_int, self._int_pan + pan_err * dt))
        tent_int_tilt = max(-max_int, min(max_int, self._int_tilt + tilt_err * dt))

        # Raw unconstrained command
        pan_cmd = (
            kp * pan_err + ki * tent_int_pan + kd * self._filt_deriv_pan + kff * los_pan_rate_deg_s
        )
        tilt_cmd = (
            kp * tilt_err
            + ki * tent_int_tilt
            + kd * self._filt_deriv_tilt
            + kff * los_tilt_rate_deg_s
        )

        # Apply conditional integration based on saturation
        if abs(pan_cmd) < vmax or _sign(pan_err) != _sign(pan_cmd):
            self._int_pan = tent_int_pan
        if abs(tilt_cmd) < vmax or _sign(tilt_err) != _sign(tilt_cmd):
            self._int_tilt = tent_int_tilt

        # Output rate clamping
        pan_rate = max(-vmax, min(vmax, pan_cmd))
        tilt_rate = max(-vmax, min(vmax, tilt_cmd))

        return {
            "pan_rate_deg_s": pan_rate,
            "tilt_rate_deg_s": tilt_rate,
            "pan_err_deg": pan_err,
            "tilt_err_deg": tilt_err,
        }


def _sign(x: float) -> int:
    """Return sign of x: -1, 0, or 1."""
    if x > 0:
        return 1
    elif x < 0:
        return -1
    return 0
