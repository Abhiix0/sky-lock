"""
Angular geometry utilities for the Sky Lock tracking system.

Provides:
- Angle wrapping and shortest-path difference
- Pixel ↔ body-frame angle conversions (pinhole camera model)

JS reference: src/tracking/geometry.js

Gimbal kinematics convention:
1. Pan rotates about local body Y by -pan.
2. Tilt rotates about local gimbal X by +tilt.
3. Camera optical axis points down -Z; +X is right, +Y is up.
4. Image pixel origin (0, 0) is top-left.
"""

from __future__ import annotations

import math

from skylock.config import CAMERA, CameraConfig


def wrap_deg(deg: float) -> float:
    """Wrap angle to (-180, 180] degrees.

    >>> wrap_deg(270)
    -90.0
    >>> wrap_deg(-270)
    90.0
    >>> wrap_deg(180)
    180.0
    """
    a = (deg + 180.0) % 360.0
    if a <= 0.0:
        a += 360.0
    return a - 180.0


def angular_diff_deg(target_deg: float, current_deg: float) -> float:
    """Shortest signed angular difference from current to target in (-180, 180] degrees.

    >>> angular_diff_deg(10, 350)
    20.0
    >>> angular_diff_deg(350, 10)
    -20.0
    """
    return wrap_deg(target_deg - current_deg)


def pixel_to_body_angles(
    px: float,
    py: float,
    pan_deg: float,
    tilt_deg: float,
    camera: CameraConfig = CAMERA,
) -> tuple[float, float]:
    """Convert pixel coordinates to body-frame pan/tilt line-of-sight angles.

    Args:
        px: Pixel X coordinate [0, width).
        py: Pixel Y coordinate [0, height).
        pan_deg: Current gimbal pan angle in degrees.
        tilt_deg: Current gimbal tilt angle in degrees.
        camera: Camera configuration.

    Returns:
        (pan_deg, tilt_deg) in body frame, wrapped to (-180, 180].
    """
    width = camera.width
    height = camera.height
    fov_deg = camera.fov_deg  # vertical FOV

    fov_rad = math.radians(fov_deg)
    focal_length = (height / 2.0) / math.tan(fov_rad / 2.0)

    cx = width / 2.0
    cy = height / 2.0

    # Normalized ray in camera space (origin top-left; py down → camY inverted)
    cam_x = (px - cx) / focal_length
    cam_y = -(py - cy) / focal_length
    cam_z = -1.0

    norm = math.hypot(cam_x, cam_y, cam_z)
    nx = cam_x / norm
    ny = cam_y / norm
    nz = cam_z / norm

    # Rotate by tilt about X (+tilt)
    tilt_rad = math.radians(tilt_deg)
    cos_t = math.cos(tilt_rad)
    sin_t = math.sin(tilt_rad)

    x_pan = nx
    y_pan = ny * cos_t - nz * sin_t
    z_pan = ny * sin_t + nz * cos_t

    # Rotate by pan about Y (-pan)
    pan_rad = math.radians(pan_deg)
    cos_p = math.cos(pan_rad)
    sin_p = math.sin(pan_rad)

    x_body = x_pan * cos_p - z_pan * sin_p
    y_body = y_pan
    z_body = x_pan * sin_p + z_pan * cos_p

    # Body-frame angles: pan = atan2(x, -z), tilt = atan2(y, hypot(x, z))
    body_pan_rad = math.atan2(x_body, -z_body)
    body_tilt_rad = math.atan2(y_body, math.hypot(x_body, z_body))

    return (
        wrap_deg(math.degrees(body_pan_rad)),
        math.degrees(body_tilt_rad),
    )


def body_angles_to_pixel(
    target_pan_deg: float,
    target_tilt_deg: float,
    gimbal_pan_deg: float,
    gimbal_tilt_deg: float,
    camera: CameraConfig = CAMERA,
) -> tuple[float, float, bool, bool]:
    """Convert body-frame pan/tilt angles to pixel coordinates on the camera sensor.

    Args:
        target_pan_deg: Target line-of-sight pan in degrees.
        target_tilt_deg: Target line-of-sight tilt in degrees.
        gimbal_pan_deg: Current gimbal pan angle in degrees.
        gimbal_tilt_deg: Current gimbal tilt angle in degrees.
        camera: Camera configuration.

    Returns:
        (px, py, in_frustum, visible_in_front)
    """
    width = camera.width
    height = camera.height
    fov_deg = camera.fov_deg

    fov_rad = math.radians(fov_deg)
    focal_length = (height / 2.0) / math.tan(fov_rad / 2.0)

    cx = width / 2.0
    cy = height / 2.0

    # Direction vector in body frame from target angles
    t_pan_rad = math.radians(target_pan_deg)
    t_tilt_rad = math.radians(target_tilt_deg)

    cos_tp = math.cos(t_pan_rad)
    sin_tp = math.sin(t_pan_rad)
    cos_tt = math.cos(t_tilt_rad)
    sin_tt = math.sin(t_tilt_rad)

    x_body = sin_tp * cos_tt
    y_body = sin_tt
    z_body = -cos_tp * cos_tt

    # Inverse pan rotation (rotate by +pan about Y)
    g_pan_rad = math.radians(gimbal_pan_deg)
    cos_gp = math.cos(g_pan_rad)
    sin_gp = math.sin(g_pan_rad)

    x_pan = x_body * cos_gp + z_body * sin_gp
    y_pan = y_body
    z_pan = -x_body * sin_gp + z_body * cos_gp

    # Inverse tilt rotation (rotate by -tilt about X)
    g_tilt_rad = math.radians(gimbal_tilt_deg)
    cos_gt = math.cos(g_tilt_rad)
    sin_gt = math.sin(g_tilt_rad)

    x_cam = x_pan
    y_cam = y_pan * cos_gt + z_pan * sin_gt
    z_cam = -y_pan * sin_gt + z_pan * cos_gt

    visible_in_front = z_cam < -1e-6

    # Project onto pinhole camera image plane
    if visible_in_front:
        px_val = cx + (x_cam / -z_cam) * focal_length
        py_val = cy - (y_cam / -z_cam) * focal_length
    else:
        px_val = cx
        py_val = cy

    in_frustum = visible_in_front and 0 <= px_val < width and 0 <= py_val < height

    return (px_val, py_val, in_frustum, visible_in_front)
