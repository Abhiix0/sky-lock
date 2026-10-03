"""Unit tests for search patterns (RasterScan and LocalSpiral)."""

from __future__ import annotations

import math

import pytest

from skylock.tracking.search_patterns import LocalSpiral, RasterScan


def test_raster_row_spacing_and_coverage() -> None:
    fov_v = 2.4
    overlap = 0.2
    expected_spacing = fov_v * (1.0 - overlap)

    raster = RasterScan(
        field_of_regard=(10.0, 8.0),
        fov=(3.0, fov_v),
        overlap=overlap,
        scan_rate=4.0,
        center=(10.0, 5.0),
    )

    assert raster.row_spacing == pytest.approx(expected_spacing)
    assert raster.num_rows > 1

    # Verify vertical spacing between consecutive row setpoints
    row_tilts: list[float] = []
    for r in range(raster.num_rows):
        t_row_start = r * raster.sweep_time + 0.001
        _pan, tilt = raster.setpoint(t_row_start)
        row_tilts.append(tilt)

    for i in range(len(row_tilts) - 1):
        spacing = row_tilts[i + 1] - row_tilts[i]
        assert spacing == pytest.approx(expected_spacing, abs=1e-5)


def test_raster_boustrophedon_alternating_direction() -> None:
    raster = RasterScan(
        field_of_regard=(10.0, 6.0),
        fov=2.0,
        overlap=0.2,
        scan_rate=5.0,
        center=(0.0, 0.0),
    )

    sweep_t = raster.sweep_time

    # Row 0 (even): should sweep in increasing pan direction
    pan_0_start, _ = raster.setpoint(0.0)
    pan_0_end, _ = raster.setpoint(sweep_t * 0.99)
    assert pan_0_end > pan_0_start

    # Row 1 (odd): should sweep in decreasing pan direction
    pan_1_start, _ = raster.setpoint(sweep_t * 1.01)
    pan_1_end, _ = raster.setpoint(sweep_t * 1.99)
    assert pan_1_end < pan_1_start


def test_spiral_stays_within_max_radius() -> None:
    center = (25.0, -10.0)
    max_radius = 2.5
    spiral = LocalSpiral(
        center=center,
        max_radius=max_radius,
        spacing=0.8,
        rate=4.0,
    )

    # At t=0, starts exactly at center
    p0, t0 = spiral.setpoint(0.0)
    assert p0 == pytest.approx(center[0])
    assert t0 == pytest.approx(center[1])

    # Sample across various times from 0 to 50 seconds
    for t in [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0]:
        pan, tilt = spiral.setpoint(t)
        dpan = pan - center[0]
        dtilt = tilt - center[1]
        dist = math.hypot(dpan, dtilt)
        assert dist <= max_radius + 1e-6, f"Spiral radius {dist} exceeded max {max_radius} at t={t}"

    # Verify is_done flag
    assert not spiral.is_done(0.0)
    assert spiral.is_done(50.0)
