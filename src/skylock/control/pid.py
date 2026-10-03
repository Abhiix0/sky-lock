"""PID controller with derivative-on-measurement filter and anti-windup."""

from __future__ import annotations


def _sign(x: float) -> int:
    """Return sign of x (-1, 0, 1)."""
    if x > 0.0:
        return 1
    if x < 0.0:
        return -1
    return 0


class PID:
    """PID controller with derivative-on-measurement filtering and anti-windup.

    Features:
    - Derivative-on-measurement to eliminate derivative kick on step setpoints
    - First-order low-pass filter on derivative term
    - Clamped integral with conditional integration (anti-windup)
    """

    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        d_alpha: float = 0.2,
        i_clamp: float = 8.0,
    ) -> None:
        """Initialize PID controller.

        Args:
            kp: Proportional gain.
            ki: Integral gain.
            kd: Derivative gain.
            d_alpha: Low-pass filter smoothing coefficient in (0, 1].
            i_clamp: Maximum absolute integral accumulator value.
        """
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.d_alpha = float(d_alpha)
        self.i_clamp = float(i_clamp)

        self.integral: float = 0.0
        self.p_term: float = 0.0
        self.i_term: float = 0.0
        self.d_term: float = 0.0

        self._prev_error: float = 0.0
        self._prev_meas: float | None = None
        self._filt_deriv: float = 0.0
        self._has_prev: bool = False

    def reset(self) -> None:
        """Reset internal accumulator and filter memories."""
        self.integral = 0.0
        self.p_term = 0.0
        self.i_term = 0.0
        self.d_term = 0.0
        self._prev_error = 0.0
        self._prev_meas = None
        self._filt_deriv = 0.0
        self._has_prev = False

    def step(
        self,
        error: float,
        dt: float,
        measurement: float | None = None,
        limit: float | None = None,
        is_saturated: bool = False,
        sat_sign: float = 0.0,
    ) -> float:
        """Execute one PID control calculation step.

        Args:
            error: Current tracking error (setpoint - measurement).
            dt: Timestep duration in seconds (must be > 0).
            measurement: Optional process variable measurement for derivative filtering.
            limit: Optional saturation limit for output clamping and anti-windup.
            is_saturated: Optional flag indicating actuator is saturated externally.
            sat_sign: Sign of external saturation (-1.0, 0.0, 1.0).

        Returns:
            Commanded control output.
        """
        if dt <= 0.0:
            return 0.0

        # 1. Proportional term
        p = self.kp * error

        # 2. Derivative term (derivative-on-measurement if measurement provided)
        if measurement is not None:
            raw_d = (
                -(measurement - self._prev_meas) / dt
                if self._prev_meas is not None
                else 0.0
            )
            self._prev_meas = measurement
        else:
            raw_d = (error - self._prev_error) / dt if self._has_prev else 0.0

        self._prev_error = error
        self._has_prev = True

        self._filt_deriv = self.d_alpha * raw_d + (1.0 - self.d_alpha) * self._filt_deriv
        d = self.kd * self._filt_deriv

        # 3. Integral term with conditional integration anti-windup
        tent_int = max(-self.i_clamp, min(self.i_clamp, self.integral + error * dt))
        u_unconstrained = p + self.ki * tent_int + d

        if is_saturated:
            if sat_sign == 0.0 or (_sign(error) == _sign(sat_sign)):
                pass  # Freeze integral accumulation
            else:
                self.integral = tent_int
        elif limit is not None and limit > 0.0:
            is_sat = abs(u_unconstrained) >= limit
            # Freeze integral if saturated in the direction of error
            if is_sat and (_sign(error) == _sign(u_unconstrained)):
                pass
            else:
                self.integral = tent_int
        else:
            self.integral = tent_int

        if limit is not None and limit > 0.0:
            u = max(-limit, min(limit, p + self.ki * self.integral + d))
        else:
            u = p + self.ki * self.integral + d

        self.p_term = p
        self.i_term = self.ki * self.integral
        self.d_term = d

        return u


__all__ = ("PID",)
