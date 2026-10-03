"""Unit tests for kinematic trajectories and motion models."""

import math

import pytest

from skylock.simulation.motion import (
    CircleTrajectory,
    Figure8Trajectory,
    LineTrajectory,
    RandomTrajectory,
)


def test_line_trajectory_constant_velocity() -> None:
    traj = LineTrajectory(start=(0.0, 0.0), speed_deg_s=2.0, heading_deg=30.0)
    p0 = traj.position(0.0)
    assert p0 == (0.0, 0.0)

    # At t=1.0 and t=2.0
    p1 = traj.position(1.0)
    p2 = traj.position(2.0)

    v1_x = p1[0] - p0[0]
    v1_y = p1[1] - p0[1]
    v2_x = p2[0] - p1[0]
    v2_y = p2[1] - p1[1]

    assert v1_x == pytest.approx(v2_x, abs=1e-9)
    assert v1_y == pytest.approx(v2_y, abs=1e-9)

    speed = math.hypot(v1_x, v1_y)
    assert speed == pytest.approx(2.0, abs=1e-9)


def test_circle_trajectory_radius_and_period() -> None:
    center = (1.0, -0.5)
    radius = 1.5
    period = 10.0
    traj = CircleTrajectory(center=center, radius_deg=radius, period_s=period, phase_rad=0.0)

    # Check radius constant at multiple times
    for t in [0.0, 1.25, 2.5, 5.0, 7.5, 9.99]:
        az, el = traj.position(t)
        dist = math.hypot(az - center[0], el - center[1])
        assert dist == pytest.approx(radius, abs=1e-9)

    # Check period: position(t + period) == position(t)
    p0 = traj.position(1.5)
    p_next = traj.position(1.5 + period)
    assert p0[0] == pytest.approx(p_next[0], abs=1e-9)
    assert p0[1] == pytest.approx(p_next[1], abs=1e-9)


def test_figure8_trajectory_properties() -> None:
    center = (0.5, 0.2)
    traj = Figure8Trajectory(center=center, width_deg=2.0, height_deg=1.0, period_s=8.0)

    # Center crossing at t=0
    p0 = traj.position(0.0)
    assert p0[0] == pytest.approx(center[0], abs=1e-9)
    assert p0[1] == pytest.approx(center[1], abs=1e-9)

    # Center crossing at half period t=4.0
    p_half = traj.position(4.0)
    assert p_half[0] == pytest.approx(center[0], abs=1e-9)
    assert p_half[1] == pytest.approx(center[1], abs=1e-9)

    # Closed curve after one period
    p_full = traj.position(8.0)
    assert p_full[0] == pytest.approx(center[0], abs=1e-9)
    assert p_full[1] == pytest.approx(center[1], abs=1e-9)


def test_random_trajectory_bounded_and_repeatable() -> None:
    bounds = (-1.0, 1.0, -0.8, 0.8)
    traj1 = RandomTrajectory(
        start=(0.0, 0.0),
        speed_deg_s=0.5,
        correlation_s=1.0,
        bounds_deg=bounds,
        seed=12345,
    )

    # Check bounds over 20 seconds
    for step in range(200):
        t = step * 0.1
        az, el = traj1.position(t)
        assert bounds[0] <= az <= bounds[1], f"Azimuth {az} out of bounds at t={t}"
        assert bounds[2] <= el <= bounds[3], f"Elevation {el} out of bounds at t={t}"

    # Query out-of-order repeatability:
    # traj2 queries t=5.0 first, then t=1.0
    traj2 = RandomTrajectory(
        start=(0.0, 0.0),
        speed_deg_s=0.5,
        correlation_s=1.0,
        bounds_deg=bounds,
        seed=12345,
    )
    p5_late = traj2.position(5.0)
    p1_late = traj2.position(1.0)

    # Fresh instance queries t=1.0 first, then t=5.0
    traj3 = RandomTrajectory(
        start=(0.0, 0.0),
        speed_deg_s=0.5,
        correlation_s=1.0,
        bounds_deg=bounds,
        seed=12345,
    )
    p1_early = traj3.position(1.0)
    p5_early = traj3.position(5.0)

    assert p1_late[0] == pytest.approx(p1_early[0], abs=1e-9)
    assert p1_late[1] == pytest.approx(p1_early[1], abs=1e-9)
    assert p5_late[0] == pytest.approx(p5_early[0], abs=1e-9)
    assert p5_late[1] == pytest.approx(p5_early[1], abs=1e-9)

    # Test reset() identically reproduces trajectory
    traj1.reset()
    p1_reset = traj1.position(1.0)
    assert p1_reset[0] == pytest.approx(p1_early[0], abs=1e-9)
    assert p1_reset[1] == pytest.approx(p1_early[1], abs=1e-9)


def test_random_trajectory_seed_sensitivity() -> None:
    bounds = (-2.0, 2.0, -2.0, 2.0)
    t_a = RandomTrajectory(
        start=(0, 0), speed_deg_s=1.0, correlation_s=1.0, bounds_deg=bounds, seed=1
    )
    t_b = RandomTrajectory(
        start=(0, 0), speed_deg_s=1.0, correlation_s=1.0, bounds_deg=bounds, seed=2
    )

    pos_a = t_a.position(3.0)
    pos_b = t_b.position(3.0)
    assert (pos_a[0] != pos_b[0]) or (pos_a[1] != pos_b[1])
