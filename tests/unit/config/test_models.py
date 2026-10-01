"""Unit tests for configuration models and derived properties."""

import pytest

from skylock.config.models import (
    CameraConfig,
    CircleMotion,
    Figure8Motion,
    GimbalConfig,
    LineMotion,
    RandomMotion,
    SkyLockConfig,
    TargetConfig,
)


def test_default_config_validity() -> None:
    cfg = SkyLockConfig()
    assert cfg.camera.width == 640
    assert cfg.camera.height == 480
    assert cfg.camera.fov_h_deg == 4.0
    assert cfg.camera.fov_v_deg == 3.0
    assert cfg.camera.fps == 30.0
    assert cfg.gimbal.slew_rate_deg_s == 5.0
    assert cfg.gimbal.max_slew_rate_deg_s == 10.0


def test_camera_derived_properties() -> None:
    cam = CameraConfig(width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0, fps=30.0)
    assert cam.ifov_h_deg == pytest.approx(0.00625)
    assert cam.ifov_v_deg == pytest.approx(0.00625)
    assert cam.frame_period_s == pytest.approx(1.0 / 30.0)
    assert cam.px_per_deg == pytest.approx(160.0)


def test_motion_models() -> None:
    line = LineMotion(speed_deg_s=1.2, heading_deg=45.0)
    assert line.kind == "line"
    assert line.speed_deg_s == 1.2

    circle = CircleMotion(radius_deg=2.0, period_s=8.0)
    assert circle.kind == "circle"

    fig8 = Figure8Motion(width_deg=2.0, height_deg=1.0)
    assert fig8.kind == "figure8"

    rand = RandomMotion(speed_deg_s=0.8)
    assert rand.kind == "random"


def test_target_config_defaults() -> None:
    target = TargetConfig()
    assert target.size_px == 10
    assert target.shape == "square"
    assert target.brightness == 220.0
    assert target.strict_spec is True


def test_gimbal_config_defaults() -> None:
    gimbal = GimbalConfig()
    assert gimbal.slew_rate_deg_s == 5.0
    assert gimbal.max_slew_rate_deg_s == 10.0
    assert gimbal.accel_deg_s2 == 120.0
    assert gimbal.substeps == 4
