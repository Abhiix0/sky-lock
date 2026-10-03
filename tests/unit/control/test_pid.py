"""Unit tests for discrete PID controller with derivative filtering and anti-windup."""

from __future__ import annotations

import pytest

from skylock.control.pid import PID


def test_pid_zero_error() -> None:
    """Zero error with zero state produces zero control output."""
    pid = PID(kp=4.0, ki=0.5, kd=0.2, d_alpha=0.8, i_clamp=2.0)
    out = pid.step(error=0.0, dt=1.0 / 30.0)
    assert out == pytest.approx(0.0)


def test_pid_proportional_response() -> None:
    """Proportional action produces Kp * error instantaneously."""
    pid = PID(kp=4.0, ki=0.0, kd=0.0, d_alpha=0.8, i_clamp=2.0)
    out = pid.step(error=2.5, dt=1.0 / 30.0)
    assert out == pytest.approx(10.0)


def test_pid_anti_windup_bounded_integral() -> None:
    """Integral accumulator is strictly clamped to i_clamp and respects anti-windup freezing."""
    i_clamp = 2.0
    pid = PID(kp=1.0, ki=5.0, kd=0.0, d_alpha=0.8, i_clamp=i_clamp)
    dt = 0.1

    # Apply persistent positive error for 100 steps
    for _ in range(100):
        pid.step(error=10.0, dt=dt, is_saturated=True, sat_sign=1.0)

    # Integral term must not exceed i_clamp
    assert abs(pid.integral) <= i_clamp + 1e-9

    # Even without external saturation, integral alone cannot exceed i_clamp
    pid.reset()
    for _ in range(100):
        pid.step(error=10.0, dt=dt, is_saturated=False)
    assert abs(pid.integral) <= i_clamp + 1e-9


def test_pid_derivative_filtering() -> None:
    """Derivative term responds to measurement rate of change filtered by d_alpha."""
    pid = PID(kp=0.0, ki=0.0, kd=1.0, d_alpha=0.5, i_clamp=2.0)
    dt = 0.1

    # First step establishes baseline measurement
    out1 = pid.step(error=1.0, dt=dt, measurement=0.0)
    assert out1 == pytest.approx(0.0)  # No delta yet

    # Second step: measurement increases by 1.0 -> d_meas/dt = 10.0
    # derivative on measurement gives -d_meas/dt = -10.0
    # filtered with alpha=0.5: raw = -10.0, filtered = 0.5 * (-10.0) = -5.0
    out2 = pid.step(error=0.0, dt=dt, measurement=1.0)
    assert out2 == pytest.approx(-5.0, abs=1e-3)


def test_pid_step_response_settling() -> None:
    """PID controlling an integrator plant settles smoothly with bounded overshoot."""
    kp = 4.0
    ki = 0.5
    kd = 0.2
    pid = PID(kp=kp, ki=ki, kd=kd, d_alpha=0.8, i_clamp=2.0)

    dt = 1.0 / 30.0
    target = 5.0
    pos = 0.0
    max_pos = 0.0

    # Run for 4 seconds (120 frames)
    for _ in range(120):
        err = target - pos
        u = pid.step(error=err, dt=dt, measurement=pos)
        # Integrator plant: dx/dt = u
        pos += u * dt
        if pos > max_pos:
            max_pos = pos

    # Target reached
    assert abs(target - pos) < 0.15
    # Overshoot < 30%
    overshoot = (max_pos - target) / target
    assert overshoot < 0.30, f"Overshoot {overshoot * 100:.1f}% exceeded 30%"


def test_pid_reset() -> None:
    """Reset clears accumulators and restores initial state."""
    pid = PID(kp=2.0, ki=1.0, kd=0.5, d_alpha=0.8, i_clamp=2.0)
    dt = 0.1

    # Accumulate state
    pid.step(error=5.0, dt=dt, measurement=1.0)
    assert pid.integral > 0.0

    pid.reset()
    assert pid.integral == pytest.approx(0.0)
    # Output on fresh step with 0 error should be 0
    out = pid.step(error=0.0, dt=dt, measurement=0.0)
    assert out == pytest.approx(0.0)
