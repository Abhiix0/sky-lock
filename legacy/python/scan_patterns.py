"""
Scan patterns for the SEARCH and REACQUIRE phases.

Provides:
- raster: Horizontal raster scan covering the full azimuth/elevation space.
- spiral: Archimedean spiral expanding from a center point.

JS reference: src/tracking/scanPatterns.js
"""

from __future__ import annotations

import math

from skylock.config import CAMERA, TRACKING, CameraConfig, TrackingConfig
from skylock.geometry import wrap_deg


def raster(
    elapsed: float,
    tracking: TrackingConfig = TRACKING,
    camera: CameraConfig = CAMERA,
) -> dict[str, float]:
    """Compute raster scan setpoint at the given elapsed time.

    The raster covers full 360° azimuth in horizontal sweeps, stepping
    vertically by (1 - overlap) * fov_deg between rows.

    Args:
        elapsed: Time since entering SEARCH in seconds.
        tracking: Tracking state machine configuration.
        camera: Camera configuration.

    Returns:
        Dict with pan_deg, tilt_deg, done (bool), cycle_time_sec.
    """
    fov_deg = camera.fov_deg
    scan_rate = min(tracking.scan_rate_deg_s, camera.max_slew_rate_deg_s)
    overlap = tracking.overlap
    tilt_limit = tracking.tilt_scan_limit_deg

    step_deg = fov_deg * (1.0 - overlap)
    if step_deg <= 0:
        step_deg = fov_deg

    # Number of tilt rows from -tilt_limit to +tilt_limit
    num_rows = max(1, math.ceil(2.0 * tilt_limit / step_deg) + 1)

    # Time for one full horizontal sweep (360°)
    sweep_time = 360.0 / scan_rate if scan_rate > 0 else 1.0

    # Time for one complete raster cycle
    cycle_time = sweep_time * num_rows

    # Current position within cycle
    t_mod = elapsed % cycle_time if cycle_time > 0 else 0.0
    row = int(t_mod / sweep_time) if sweep_time > 0 else 0
    row = min(row, num_rows - 1)

    t_in_row = t_mod - row * sweep_time
    frac = t_in_row / sweep_time if sweep_time > 0 else 0.0

    # Alternate sweep direction for even/odd rows
    if row % 2 == 0:
        pan_deg = -180.0 + frac * 360.0
    else:
        pan_deg = 180.0 - frac * 360.0

    # Tilt position
    tilt_deg = -tilt_limit + row * step_deg
    tilt_deg = max(-tilt_limit, min(tilt_limit, tilt_deg))

    return {
        "pan_deg": wrap_deg(pan_deg),
        "tilt_deg": tilt_deg,
        "done": False,  # raster repeats indefinitely
        "cycle_time_sec": cycle_time,
    }


def spiral(
    elapsed: float,
    center: dict[str, float],
    tracking: TrackingConfig = TRACKING,
    camera: CameraConfig = CAMERA,
) -> dict[str, float]:
    """Compute Archimedean spiral setpoint expanding from a center point.

    Used in REACQUIRE to search around the last known target position.

    Args:
        elapsed: Time since entering REACQUIRE in seconds.
        center: Dict with pan_deg, tilt_deg of the spiral center.
        tracking: Tracking state machine configuration.
        camera: Camera configuration.

    Returns:
        Dict with pan_deg, tilt_deg, done (bool).
    """
    fov_deg = camera.fov_deg
    max_radius = tracking.reacquire_max_radius_deg
    scan_rate = min(tracking.scan_rate_deg_s, camera.max_slew_rate_deg_s)

    if scan_rate <= 0 or max_radius <= 0:
        return {
            "pan_deg": center.get("pan_deg", 0.0),
            "tilt_deg": center.get("tilt_deg", 0.0),
            "done": True,
        }

    # Spiral parameters
    # Angular velocity in the spiral plane
    omega = scan_rate / max(fov_deg, 0.1) * 2.0 * math.pi

    # Arm spacing: one FOV width per revolution
    arm_spacing = fov_deg * (1.0 - tracking.overlap)
    if arm_spacing <= 0:
        arm_spacing = fov_deg

    # Growth rate: degrees per radian of angle
    growth = arm_spacing / (2.0 * math.pi)

    theta = omega * elapsed
    radius = growth * theta

    if radius > max_radius:
        return {
            "pan_deg": center.get("pan_deg", 0.0),
            "tilt_deg": center.get("tilt_deg", 0.0),
            "done": True,
        }

    pan_offset = radius * math.cos(theta)
    tilt_offset = radius * math.sin(theta)

    return {
        "pan_deg": wrap_deg(center.get("pan_deg", 0.0) + pan_offset),
        "tilt_deg": center.get("tilt_deg", 0.0) + tilt_offset,
        "done": False,
    }
