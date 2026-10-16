"""Unit tests for authoritative Line-of-Sight (LOS) geometry and Earth-occlusion.

Phase 5.4 requirements:
- A clear segment outside the Earth sphere.
- A segment intersecting the Earth sphere.
- A segment tangent to Earth.
- A segment whose infinite extension intersects Earth but whose finite segment does not.
- Satellites moving while LOS remains clear.
- LOS changing from clear to blocked and back to clear.
- Both S-1-to-S-2 and S-2-to-S-1 geometry.
- Line endpoints remaining synchronized with rendered satellite positions.
- Application startup producing a valid initial LOS calculation.
"""

from __future__ import annotations

import math

import numpy as np

from skylock.core.los import (
    calculate_look_angles,
    check_line_of_sight,
    get_satellite_position,
    orbit_position_at_time,
)
from skylock.core.orbital_world import S1_DEFAULT_ORBIT, S2_DEFAULT_ORBIT


class TestLOSGeometryScenarios:
    """Rigorous geometric test suite for segment-sphere LOS occlusion."""

    BODY_RADIUS = 10.0

    def test_1_clear_segment_outside_earth(self) -> None:
        """Scenario 1: Finite segment completely clears Earth sphere."""
        # Horizontal segment at y = 15.0 (Earth R = 10.0)
        p1 = (-20.0, 15.0, 0.0)
        p2 = (20.0, 15.0, 0.0)
        assert check_line_of_sight(p1, p2, body_radius=self.BODY_RADIUS)

        # Another clear diagonal segment in +Z hemisphere
        p3 = (0.0, 12.0, 12.0)
        p4 = (12.0, 0.0, 12.0)
        assert check_line_of_sight(p3, p4, body_radius=self.BODY_RADIUS)

    def test_2_segment_intersecting_earth_sphere(self) -> None:
        """Scenario 2: Segment passes directly through or penetrates Earth."""
        # Passes straight through origin
        p1 = (-15.0, 0.0, 0.0)
        p2 = (15.0, 0.0, 0.0)
        assert not check_line_of_sight(p1, p2, body_radius=self.BODY_RADIUS)

        # Passes through at y = 5.0 (inside R = 10.0)
        p3 = (-12.0, 5.0, 0.0)
        p4 = (12.0, 5.0, 0.0)
        assert not check_line_of_sight(p3, p4, body_radius=self.BODY_RADIUS)

    def test_3_segment_tangent_to_earth(self) -> None:
        """Scenario 3: Segment tangent to Earth surface within documented tolerance."""
        # Grazing just slightly above (10.0 + 1e-4) -> must be CLEAR
        p1_above = (-20.0, 10.0001, 0.0)
        p2_above = (20.0, 10.0001, 0.0)
        assert check_line_of_sight(p1_above, p2_above, body_radius=self.BODY_RADIUS)

        # Penetrating slightly below (10.0 - 1e-4) -> must be BLOCKED
        p1_below = (-20.0, 9.9999, 0.0)
        p2_below = (20.0, 9.9999, 0.0)
        assert not check_line_of_sight(p1_below, p2_below, body_radius=self.BODY_RADIUS)

    def test_4_infinite_extension_intersects_but_finite_segment_clears(self) -> None:
        """Scenario 4: Infinite line would pierce Earth, but segment is on one side."""
        # Infinite line along x-axis passes through origin (0, 0, 0)
        # But segment is from x=12.0 to x=25.0 (both points outside R=10.0 on positive x-axis)
        p1 = (12.0, 0.0, 0.0)
        p2 = (25.0, 0.0, 0.0)
        assert check_line_of_sight(p1, p2, body_radius=self.BODY_RADIUS)

        # Segment from x=-30.0 to x=-12.0 on negative side
        p3 = (-30.0, 0.0, 0.0)
        p4 = (-12.0, 0.0, 0.0)
        assert check_line_of_sight(p3, p4, body_radius=self.BODY_RADIUS)

    def test_5_satellites_moving_while_los_remains_clear(self) -> None:
        """Scenario 5: Satellites move over a continuous time window with unobstructed LOS."""
        # For our default orbits, t=0 to t=50s has clear LOS uninterrupted
        for t_s in np.linspace(0.0, 50.0, 25):
            p1 = get_satellite_position("s1", t_s)
            p2 = get_satellite_position("s2", t_s)
            assert check_line_of_sight(p1, p2, body_radius=self.BODY_RADIUS)

    def test_6_los_transitions_clear_blocked_clear(self) -> None:
        """Scenario 6: Full orbital period demonstrates CLEAR -> BLOCKED -> CLEAR cycle."""
        # Sample from t=100s to t=250s where occultation begins (~118s) and recovers
        t_values = np.linspace(100.0, 250.0, 151)
        los_series = [
            check_line_of_sight(
                get_satellite_position("s1", t),
                get_satellite_position("s2", t),
                body_radius=self.BODY_RADIUS,
            )
            for t in t_values
        ]

        # Verify we observe transitions
        transitions = sum(
            1 for i in range(len(los_series) - 1) if los_series[i] != los_series[i + 1]
        )
        assert transitions >= 2, (
            f"Expected at least 2 transitions (clear->blocked->clear), got {transitions}"
        )
        assert any(los_series), "Should have clear states"
        assert any(not s for s in los_series), "Should have blocked states"

    def test_7_bidirectional_los_symmetry(self) -> None:
        """Scenario 7: LOS(p1, p2) == LOS(p2, p1) for all tested geometries."""
        test_pairs = [
            ((-15.0, 0.0, 0.0), (15.0, 0.0, 0.0)),
            ((15.0, 15.0, 0.0), (-15.0, 15.0, 0.0)),
            ((12.0, 0.0, 0.0), (25.0, 0.0, 0.0)),
            (get_satellite_position("s1", 125.0), get_satellite_position("s2", 125.0)),
            (get_satellite_position("s1", 10.0), get_satellite_position("s2", 10.0)),
        ]
        for p1, p2 in test_pairs:
            forward = check_line_of_sight(p1, p2, body_radius=self.BODY_RADIUS)
            reverse = check_line_of_sight(p2, p1, body_radius=self.BODY_RADIUS)
            assert forward == reverse, f"Asymmetry detected for pair {p1} <-> {p2}"

    def test_8_line_endpoints_synchronized_with_satellite_positions(self) -> None:
        """Scenario 8: Line endpoints match authoritative satellite positions exactly."""
        for t_s in [0.0, 15.5, 42.0, 120.0]:
            p1_calc = orbit_position_at_time(S1_DEFAULT_ORBIT, t_s)
            p1_get = get_satellite_position("s1", t_s)
            assert np.allclose(p1_calc, p1_get, atol=1e-6)

            p2_calc = orbit_position_at_time(S2_DEFAULT_ORBIT, t_s)
            p2_get = get_satellite_position("s2", t_s)
            assert np.allclose(p2_calc, p2_get, atol=1e-6)

            # Look angles match vector difference
            _, _, dist = calculate_look_angles(p1_get, p2_get)
            dx = p2_get[0] - p1_get[0]
            dy = p2_get[1] - p1_get[1]
            dz = p2_get[2] - p1_get[2]
            assert math.isclose(dist, math.sqrt(dx**2 + dy**2 + dz**2), rel_tol=1e-5)

    def test_9_application_startup_produces_valid_los(self) -> None:
        """Scenario 9: At t=0.0 (startup), produces a valid initial LOS calculation."""
        p1_0 = get_satellite_position("s1", 0.0)
        p2_0 = get_satellite_position("s2", 0.0)

        # Initial distance and positions are valid finite floats
        assert all(math.isfinite(x) for x in p1_0)
        assert all(math.isfinite(x) for x in p2_0)

        initial_los = check_line_of_sight(p1_0, p2_0, body_radius=self.BODY_RADIUS)
        # At t=0, S1 is at (20, 0, 0) and S2 is clear of Earth
        assert initial_los is True, "Startup configuration should have unobstructed line of sight"
