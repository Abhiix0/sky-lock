"""Tests for skylock.geometry — angle wrapping and pixel↔body transforms."""

import pytest

from skylock.config import CameraConfig
from skylock.geometry import (
    angular_diff_deg,
    body_angles_to_pixel,
    pixel_to_body_angles,
    wrap_deg,
)


class TestWrapDeg:
    """Angle wrapping to (-180, 180]."""

    def test_identity_in_range(self):
        assert wrap_deg(45.0) == pytest.approx(45.0)

    def test_wrap_positive_overflow(self):
        assert wrap_deg(270.0) == pytest.approx(-90.0)

    def test_wrap_negative_overflow(self):
        assert wrap_deg(-270.0) == pytest.approx(90.0)

    def test_wrap_180_stays(self):
        assert wrap_deg(180.0) == pytest.approx(180.0)

    def test_wrap_360(self):
        assert wrap_deg(360.0) == pytest.approx(0.0)

    def test_wrap_negative_360(self):
        assert wrap_deg(-360.0) == pytest.approx(0.0)

    def test_wrap_zero(self):
        assert wrap_deg(0.0) == pytest.approx(0.0)

    @pytest.mark.parametrize("deg", [-720, -540, -180, 0, 180, 540, 720])
    def test_wrap_multiples_of_180(self, deg):
        result = wrap_deg(float(deg))
        assert -180.0 < result <= 180.0


class TestAngularDiffDeg:
    """Shortest signed angular difference."""

    def test_positive_short_path(self):
        assert angular_diff_deg(10.0, 350.0) == pytest.approx(20.0)

    def test_negative_short_path(self):
        assert angular_diff_deg(350.0, 10.0) == pytest.approx(-20.0)

    def test_same_angle(self):
        assert angular_diff_deg(90.0, 90.0) == pytest.approx(0.0)

    def test_opposite_angles(self):
        result = angular_diff_deg(0.0, 180.0)
        assert abs(result) == pytest.approx(180.0)


class TestPixelToBodyAngles:
    """Pixel coordinate to body-frame angle conversion."""

    def test_center_pixel_returns_gimbal_angles(self):
        """Center pixel should map to the gimbal boresight direction."""
        cam = CameraConfig(fov_v_deg=20.0, width=640, height=480)
        pan, tilt = pixel_to_body_angles(320.0, 240.0, 45.0, 10.0, cam)
        assert pan == pytest.approx(45.0, abs=0.1)
        assert tilt == pytest.approx(10.0, abs=0.1)

    def test_zero_gimbal_center(self):
        """At zero gimbal, center pixel should give (0, 0)."""
        cam = CameraConfig(fov_v_deg=20.0, width=640, height=480)
        pan, tilt = pixel_to_body_angles(320.0, 240.0, 0.0, 0.0, cam)
        assert pan == pytest.approx(0.0, abs=0.01)
        assert tilt == pytest.approx(0.0, abs=0.01)

    def test_off_center_pixel_displaces_angle(self):
        """Pixel off center should produce angular offset from boresight."""
        cam = CameraConfig(fov_v_deg=20.0, width=640, height=480)
        # Pixel to the right of center
        pan_right, _ = pixel_to_body_angles(400.0, 240.0, 0.0, 0.0, cam)
        # Should be positive pan (right of boresight)
        assert pan_right > 0.0


class TestBodyAnglesToPixel:
    """Body-frame angle to pixel coordinate conversion."""

    def test_boresight_maps_to_center(self):
        """Gimbal boresight should project to center pixel."""
        cam = CameraConfig(fov_v_deg=20.0, width=640, height=480)
        px, py, in_frustum, visible = body_angles_to_pixel(45.0, 10.0, 45.0, 10.0, cam)
        assert px == pytest.approx(320.0, abs=0.5)
        assert py == pytest.approx(240.0, abs=0.5)
        assert in_frustum is True
        assert visible is True

    def test_roundtrip_consistency(self):
        """pixel→body→pixel should be identity (within frustum)."""
        cam = CameraConfig(fov_v_deg=20.0, width=640, height=480)
        # Start with a pixel near center
        px_in, py_in = 350.0, 260.0
        gimbal_pan, gimbal_tilt = 30.0, 15.0

        body_pan, body_tilt = pixel_to_body_angles(px_in, py_in, gimbal_pan, gimbal_tilt, cam)
        px_out, py_out, in_frustum, _ = body_angles_to_pixel(
            body_pan, body_tilt, gimbal_pan, gimbal_tilt, cam
        )

        assert in_frustum is True
        assert px_out == pytest.approx(px_in, abs=0.1)
        assert py_out == pytest.approx(py_in, abs=0.1)

    def test_target_behind_camera_not_visible(self):
        """Target 180° away from gimbal should not be visible."""
        cam = CameraConfig(fov_v_deg=20.0, width=640, height=480)
        _, _, in_frustum, visible = body_angles_to_pixel(180.0, 0.0, 0.0, 0.0, cam)
        assert visible is False
        assert in_frustum is False
