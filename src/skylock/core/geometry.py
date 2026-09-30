"""Angular geometry, wrapping, and tangent-plane projection utilities for SkyLock."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skylock.config.models import CameraConfig


def wrap_deg(deg: float) -> float:
    """Wrap angle in degrees to (-180, 180].

    >>> wrap_deg(270.0)
    -90.0
    >>> wrap_deg(-270.0)
    90.0
    >>> wrap_deg(180.0)
    180.0
    """
    a = (deg + 180.0) % 360.0
    if a <= 0.0:
        a += 360.0
    return a - 180.0


def angular_diff_deg(target_deg: float, current_deg: float) -> float:
    """Shortest signed angular difference from current to target in (-180, 180].

    >>> angular_diff_deg(10.0, 350.0)
    20.0
    >>> angular_diff_deg(350.0, 10.0)
    -20.0
    """
    return wrap_deg(target_deg - current_deg)


def pixel_to_angle_offset(
    px: float,
    py: float,
    cam: CameraConfig,
) -> tuple[float, float]:
    """Convert pixel coordinates to tangent-plane angular offsets from camera boresight.

    Conventions:
    - Pixel origin (0, 0) is top-left.
    - Boresight is ((width - 1)/2, (height - 1)/2).
    - +dpan (degrees) is to the right (+X in image).
    - +dtilt (degrees) is up (-Y in image).

    Returns:
        (dpan_deg, dtilt_deg)
    """
    cx = (cam.width - 1.0) / 2.0
    cy = (cam.height - 1.0) / 2.0

    fx = (cam.width / 2.0) / math.tan(math.radians(cam.fov_h_deg / 2.0))
    fy = (cam.height / 2.0) / math.tan(math.radians(cam.fov_v_deg / 2.0))

    dx = px - cx
    dy = -(py - cy)  # Upwards tilt corresponds to lower image row (y)

    dpan = math.degrees(math.atan(dx / fx))
    dtilt = math.degrees(math.atan(dy / fy))

    return (dpan, dtilt)


def angle_offset_to_pixel(
    dpan_deg: float,
    dtilt_deg: float,
    cam: CameraConfig,
) -> tuple[float, float]:
    """Convert tangent-plane angular offsets to camera pixel coordinates.

    Returns:
        (px, py)
    """
    cx = (cam.width - 1.0) / 2.0
    cy = (cam.height - 1.0) / 2.0

    fx = (cam.width / 2.0) / math.tan(math.radians(cam.fov_h_deg / 2.0))
    fy = (cam.height / 2.0) / math.tan(math.radians(cam.fov_v_deg / 2.0))

    dx = fx * math.tan(math.radians(dpan_deg))
    dy = fy * math.tan(math.radians(dtilt_deg))

    px = cx + dx
    py = cy - dy

    return (px, py)
