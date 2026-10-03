"""
Physically limited 2-axis gimbal servo controller.

Simulates pan/tilt actuator dynamics with:
- Acceleration-limited velocity profiles
- Joint limits with clamping
- Pan wrap-around across ±180°
- GOTO (position) and RATE (velocity) command modes

JS reference: src/tracking/gimbal.js
"""

from __future__ import annotations

import math

from skylock.config import CAMERA, CameraConfig
from skylock.geometry import angular_diff_deg, wrap_deg


class Gimbal:
    """Two-axis gimbal servo with physically-limited dynamics.

    Args:
        camera: Camera and gimbal configuration.
        initial_pan: Initial pan angle in degrees.
        initial_tilt: Initial tilt angle in degrees.
    """

    def __init__(
        self,
        camera: CameraConfig = CAMERA,
        initial_pan: float = 90.0,
        initial_tilt: float = 0.0,
    ) -> None:
        self._camera = camera
        self._pan_limit = camera.pan_limit_deg
        self._tilt_limit = camera.tilt_limit_deg
        self._pan_wrap = camera.pan_wrap
        self._accel_limit = camera.max_slew_accel_deg_s2

        self._pan: float = initial_pan
        self._tilt: float = initial_tilt
        self._pan_rate: float = 0.0
        self._tilt_rate: float = 0.0

        self._mode: str = "GOTO"
        self._target_pan: float = initial_pan
        self._target_tilt: float = initial_tilt
        self._cmd_pan_rate: float = 0.0
        self._cmd_tilt_rate: float = 0.0

        self._at_limit_pan: bool = False
        self._at_limit_tilt: bool = False

    @property
    def max_slew_rate(self) -> float:
        """Effective maximum slew velocity in deg/s."""
        return self._camera.max_slew_rate_deg_s

    def set_command(self, pan_deg: float, tilt_deg: float) -> None:
        """Command target angles for go-to mode.

        Args:
            pan_deg: Desired pan in degrees.
            tilt_deg: Desired tilt in degrees.
        """
        self._mode = "GOTO"
        if self._pan_wrap:
            self._target_pan = wrap_deg(pan_deg)
        else:
            self._target_pan = max(-self._pan_limit, min(self._pan_limit, pan_deg))
        self._target_tilt = max(-self._tilt_limit, min(self._tilt_limit, tilt_deg))

    def set_rate_command(self, pan_rate_deg_s: float, tilt_rate_deg_s: float) -> None:
        """Command angular rates for rate mode.

        Args:
            pan_rate_deg_s: Desired pan rate in deg/s.
            tilt_rate_deg_s: Desired tilt rate in deg/s.
        """
        self._mode = "RATE"
        self._cmd_pan_rate = pan_rate_deg_s
        self._cmd_tilt_rate = tilt_rate_deg_s

    def snap_to(self, pan_deg: float, tilt_deg: float) -> None:
        """Instantly snap gimbal to angles (debug/reset only).

        Args:
            pan_deg: Target pan angle.
            tilt_deg: Target tilt angle.
        """
        if self._pan_wrap:
            self._pan = wrap_deg(pan_deg)
        else:
            self._pan = max(-self._pan_limit, min(self._pan_limit, pan_deg))
        self._tilt = max(-self._tilt_limit, min(self._tilt_limit, tilt_deg))
        self._pan_rate = 0.0
        self._tilt_rate = 0.0
        self._target_pan = self._pan
        self._target_tilt = self._tilt
        self._cmd_pan_rate = 0.0
        self._cmd_tilt_rate = 0.0

    def step(self, dt: float) -> None:
        """Advance gimbal servo dynamics by fixed timestep.

        Args:
            dt: Timestep in seconds (must be > 0).
        """
        if dt <= 0.0:
            return

        vmax = self.max_slew_rate
        a = self._accel_limit
        max_dv = a * dt

        # --- PAN AXIS ---
        if self._mode == "GOTO":
            if self._pan_wrap:
                err = angular_diff_deg(self._target_pan, self._pan)
            else:
                err = self._target_pan - self._pan
            abs_err = abs(err)
            if abs_err < 0.0001 and abs(self._pan_rate) < 0.001:
                self._pan = self._target_pan
                self._pan_rate = 0.0
                desired_pan_vel = 0.0
            else:
                desired_pan_vel = _sign_f(err) * min(vmax, math.sqrt(max(0.0, 2.0 * a * abs_err)))
        else:
            desired_pan_vel = max(-vmax, min(vmax, self._cmd_pan_rate))

        d_pan_v = desired_pan_vel - self._pan_rate
        self._pan_rate += max(-max_dv, min(max_dv, d_pan_v))
        self._pan += self._pan_rate * dt

        if self._pan_wrap:
            self._pan = wrap_deg(self._pan)
            self._at_limit_pan = False
        else:
            if self._pan >= self._pan_limit:
                self._pan = self._pan_limit
                self._at_limit_pan = True
                if self._pan_rate > 0:
                    self._pan_rate = 0.0
            elif self._pan <= -self._pan_limit:
                self._pan = -self._pan_limit
                self._at_limit_pan = True
                if self._pan_rate < 0:
                    self._pan_rate = 0.0
            else:
                self._at_limit_pan = False

        # --- TILT AXIS ---
        if self._mode == "GOTO":
            err = self._target_tilt - self._tilt
            abs_err = abs(err)
            if abs_err < 0.0001 and abs(self._tilt_rate) < 0.001:
                self._tilt = self._target_tilt
                self._tilt_rate = 0.0
                desired_tilt_vel = 0.0
            else:
                desired_tilt_vel = _sign_f(err) * min(vmax, math.sqrt(max(0.0, 2.0 * a * abs_err)))
        else:
            desired_tilt_vel = max(-vmax, min(vmax, self._cmd_tilt_rate))

        d_tilt_v = desired_tilt_vel - self._tilt_rate
        self._tilt_rate += max(-max_dv, min(max_dv, d_tilt_v))
        self._tilt += self._tilt_rate * dt

        if self._tilt >= self._tilt_limit:
            self._tilt = self._tilt_limit
            self._at_limit_tilt = True
            if self._tilt_rate > 0:
                self._tilt_rate = 0.0
        elif self._tilt <= -self._tilt_limit:
            self._tilt = -self._tilt_limit
            self._at_limit_tilt = True
            if self._tilt_rate < 0:
                self._tilt_rate = 0.0
        else:
            self._at_limit_tilt = False

    def get_state(self) -> dict[str, float | str | bool]:
        """Return current gimbal state.

        Returns:
            Dict with pan_deg, tilt_deg, pan_rate_deg_s, tilt_rate_deg_s,
            mode, at_limit_pan, at_limit_tilt.
        """
        return {
            "pan_deg": self._pan,
            "tilt_deg": self._tilt,
            "pan_rate_deg_s": self._pan_rate,
            "tilt_rate_deg_s": self._tilt_rate,
            "mode": self._mode,
            "at_limit_pan": self._at_limit_pan,
            "at_limit_tilt": self._at_limit_tilt,
        }

    def reset(self, pan_deg: float = 90.0, tilt_deg: float = 0.0) -> None:
        """Reset gimbal to initial state.

        Args:
            pan_deg: Initial pan angle.
            tilt_deg: Initial tilt angle.
        """
        self.snap_to(pan_deg, tilt_deg)
        self._mode = "GOTO"
        self._at_limit_pan = False
        self._at_limit_tilt = False


def run_gimbal_self_test(
    camera: CameraConfig = CAMERA,
    dt: float = 1.0 / 120.0,
) -> dict[str, float]:
    """Self-test routine for gimbal servo response and seam crossing.

    Args:
        camera: Camera/gimbal configuration.
        dt: Simulation timestep.

    Returns:
        Dict with max_rate, max_accel, overshoot_deg, seam_path_deg.
    """
    gimbal = Gimbal(camera=camera, initial_pan=0.0, initial_tilt=0.0)

    # Test 1: 90° pan step from 0 to 90
    gimbal.snap_to(0.0, 0.0)
    gimbal.set_command(90.0, 0.0)

    max_rate = 0.0
    max_accel = 0.0
    prev_rate = 0.0
    max_pan_observed = 0.0

    for _ in range(600):  # up to 5 seconds
        gimbal.step(dt)
        st = gimbal.get_state()
        rate = abs(st["pan_rate_deg_s"])
        if rate > max_rate:
            max_rate = rate

        accel = abs(rate - prev_rate) / dt
        if accel > max_accel:
            max_accel = accel
        prev_rate = rate

        if st["pan_deg"] > max_pan_observed:
            max_pan_observed = st["pan_deg"]
        if abs(st["pan_deg"] - 90.0) < 0.001 and rate < 0.001:
            break

    overshoot_deg = max(0.0, max_pan_observed - 90.0)

    # Test 2: Seam crossing from 179° to -179°
    gimbal.snap_to(179.0, 0.0)
    gimbal.set_command(-179.0, 0.0)

    total_path_deg = 0.0
    last_p = 179.0

    for _ in range(240):
        gimbal.step(dt)
        st = gimbal.get_state()
        dp = abs(angular_diff_deg(st["pan_deg"], last_p))
        total_path_deg += dp
        last_p = st["pan_deg"]
        if abs(angular_diff_deg(-179.0, st["pan_deg"])) < 0.01 and abs(st["pan_rate_deg_s"]) < 0.01:
            break

    return {
        "max_rate": max_rate,
        "max_accel": max_accel,
        "overshoot_deg": overshoot_deg,
        "seam_path_deg": total_path_deg,
    }


def _sign_f(x: float) -> float:
    """Return sign of x as float: -1.0, 0.0, or 1.0."""
    if x > 0:
        return 1.0
    elif x < 0:
        return -1.0
    return 0.0
