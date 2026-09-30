"""Unit tests for geometry, angle wrapping, and tangent-plane conversions."""

import pytest

from skylock.config.models import CameraConfig
from skylock.core.geometry import (
    angle_offset_to_pixel,
    angular_diff_deg,
    pixel_to_angle_offset,
    wrap_deg,
)


class TestWrapDeg:
    """Ported and verified angle wrapping tests."""

    def test_identity_in_range(self) -> None:
        assert wrap_deg(45.0) == pytest.approx(45.0)

    def test_wrap_positive_overflow(self) -> None:
        assert wrap_deg(270.0) == pytest.approx(-90.0)

    def test_wrap_negative_overflow(self) -> None:
        assert wrap_deg(-270.0) == pytest.approx(90.0)

    def test_wrap_180_stays(self) -> None:
        assert wrap_deg(180.0) == pytest.approx(180.0)

    def test_wrap_360(self) -> None:
        assert wrap_deg(360.0) == pytest.approx(0.0)

    def test_wrap_negative_360(self) -> None:
        assert wrap_deg(-360.0) == pytest.approx(0.0)

    def test_wrap_zero(self) -> None:
        assert wrap_deg(0.0) == pytest.approx(0.0)

    @pytest.mark.parametrize("deg", [-720, -540, -180, 0, 180, 540, 720])
    def test_wrap_multiples_of_180(self, deg: float) -> None:
        result = wrap_deg(float(deg))
        assert -180.0 < result <= 180.0


class TestAngularDiffDeg:
    """Ported and verified shortest angular difference tests."""

    def test_positive_short_path(self) -> None:
        assert angular_diff_deg(10.0, 350.0) == pytest.approx(20.0)

    def test_negative_short_path(self) -> None:
        assert angular_diff_deg(350.0, 10.0) == pytest.approx(-20.0)

    def test_same_angle(self) -> None:
        assert angular_diff_deg(90.0, 90.0) == pytest.approx(0.0)

    def test_opposite_angles(self) -> None:
        result = angular_diff_deg(0.0, 180.0)
        assert abs(result) == pytest.approx(180.0)


class TestTangentPlaneConversions:
    """Tangent plane pixel ↔ angular offset conversions."""

    @pytest.fixture
    def cam(self) -> CameraConfig:
        return CameraConfig(width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0)

    def test_boresight_mapping(self, cam: CameraConfig) -> None:
        cx = (cam.width - 1.0) / 2.0
        cy = (cam.height - 1.0) / 2.0
        dpan, dtilt = pixel_to_angle_offset(cx, cy, cam)
        assert dpan == pytest.approx(0.0, abs=1e-12)
        assert dtilt == pytest.approx(0.0, abs=1e-12)

        px, py = angle_offset_to_pixel(0.0, 0.0, cam)
        assert px == pytest.approx(cx, abs=1e-12)
        assert py == pytest.approx(cy, abs=1e-12)

    def test_conventions_direction(self, cam: CameraConfig) -> None:
        cx = (cam.width - 1.0) / 2.0
        cy = (cam.height - 1.0) / 2.0

        # Pixel to the right (+X) -> +dpan
        dpan_right, _ = pixel_to_angle_offset(cx + 50.0, cy, cam)
        assert dpan_right > 0.0

        # Pixel upwards (lower Y coordinate in image) -> +dtilt
        _, dtilt_up = pixel_to_angle_offset(cx, cy - 50.0, cam)
        assert dtilt_up > 0.0

    @pytest.mark.parametrize("px,py", [(0.0, 0.0), (320.0, 240.0), (639.0, 479.0), (100.5, 380.25)])
    def test_roundtrip_precision(self, px: float, py: float, cam: CameraConfig) -> None:
        dpan, dtilt = pixel_to_angle_offset(px, py, cam)
        rx, ry = angle_offset_to_pixel(dpan, dtilt, cam)
        assert rx == pytest.approx(px, abs=1e-9)
        assert ry == pytest.approx(py, abs=1e-9)
