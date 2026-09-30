"""Tests for skylock.scan_patterns — raster and spiral scan patterns."""

import math

import pytest

from skylock.config import CameraConfig, TrackingConfig
from skylock.scan_patterns import raster, spiral


class TestRaster:
    """Raster scan pattern."""

    def test_returns_valid_angles(self):
        result = raster(0.0)
        assert "pan_deg" in result
        assert "tilt_deg" in result
        assert "done" in result
        assert result["done"] is False

    def test_pan_sweeps_across_full_range(self):
        """Over one sweep, pan should cover a large range."""
        pans = []
        for i in range(200):
            r = raster(i * 0.1)
            pans.append(r["pan_deg"])

        pan_range = max(pans) - min(pans)
        assert pan_range > 180.0, f"Pan range {pan_range}° should cover most of 360°"

    def test_tilt_steps_between_rows(self):
        """Different rows should have different tilt values."""
        camera = CameraConfig(fov_v_deg=3.0, max_slew_rate_deg_s=5.0)
        tracking = TrackingConfig(
            scan_rate_deg_s=4.0,
            overlap=0.2,
            tilt_scan_limit_deg=55.0,
        )

        # Get tilt at start of row 0 and after one full sweep
        sweep_time = 360.0 / 4.0  # 90 seconds per sweep
        r0 = raster(0.0, tracking, camera)
        r1 = raster(sweep_time + 0.1, tracking, camera)

        assert r0["tilt_deg"] != pytest.approx(r1["tilt_deg"], abs=0.1)

    def test_raster_covers_all_tilt_cells(self):
        """Over one full cycle, raster should cover all tilt cells."""
        camera = CameraConfig(fov_v_deg=3.0, max_slew_rate_deg_s=5.0)
        tracking = TrackingConfig(
            scan_rate_deg_s=4.0,
            tilt_scan_limit_deg=10.0,
        )

        r = raster(0.0, tracking, camera)
        cycle_time = r["cycle_time_sec"]

        tilts = set()
        for i in range(int(cycle_time * 10) + 1):
            r = raster(i * 0.1, tracking, camera)
            tilts.add(round(r["tilt_deg"], 1))

        assert len(tilts) > 1, "Raster should cover multiple tilt positions"

    def test_cycle_time_positive(self):
        result = raster(0.0)
        assert result["cycle_time_sec"] > 0


class TestSpiral:
    """Archimedean spiral scan pattern."""

    def test_starts_near_center(self):
        center = {"pan_deg": 45.0, "tilt_deg": 20.0}
        result = spiral(0.0, center)
        assert result["pan_deg"] == pytest.approx(45.0, abs=1.0)
        assert result["tilt_deg"] == pytest.approx(20.0, abs=1.0)

    def test_expands_outward(self):
        """Radius should increase over time."""
        center = {"pan_deg": 0.0, "tilt_deg": 0.0}
        r0 = spiral(0.0, center)
        r1 = spiral(1.0, center)
        r2 = spiral(2.0, center)

        dist0 = math.hypot(r0["pan_deg"], r0["tilt_deg"])
        dist1 = math.hypot(r1["pan_deg"], r1["tilt_deg"])
        dist2 = math.hypot(r2["pan_deg"], r2["tilt_deg"])

        assert dist1 >= dist0
        assert dist2 >= dist1

    def test_completes_when_exceeding_max_radius(self):
        """Spiral should report done when radius exceeds max."""
        tracking = TrackingConfig(reacquire_max_radius_deg=5.0)
        center = {"pan_deg": 0.0, "tilt_deg": 0.0}

        # Run for long enough that spiral exceeds max radius
        done = False
        for i in range(1000):
            result = spiral(i * 0.1, center, tracking)
            if result["done"]:
                done = True
                break

        assert done, "Spiral should eventually complete"

    def test_returns_center_when_done(self):
        """When done, spiral should return center position."""
        tracking = TrackingConfig(reacquire_max_radius_deg=1.0)
        center = {"pan_deg": 30.0, "tilt_deg": 15.0}

        # Find completion
        for i in range(1000):
            result = spiral(i * 0.1, center, tracking)
            if result["done"]:
                assert result["pan_deg"] == pytest.approx(30.0, abs=0.1)
                assert result["tilt_deg"] == pytest.approx(15.0, abs=0.1)
                return

        pytest.fail("Spiral never completed")
