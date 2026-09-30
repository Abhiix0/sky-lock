"""Unit tests for configuration validation and violation aggregation."""

import pytest

from skylock.config.models import (
    CameraConfig,
    ControlConfig,
    DisturbanceConfig,
    GaussianConfig,
    GimbalConfig,
    JitterConfig,
    PlatformConfig,
    RequirementsConfig,
    SkyLockConfig,
    TargetConfig,
    TrackingConfig,
)
from skylock.config.validation import ConfigError


def test_square_pixel_mismatch() -> None:
    # 4 deg / 640 = 0.00625, but 4 deg / 480 = 0.00833 (mismatch > 1%)
    with pytest.raises(ConfigError) as exc_info:
        CameraConfig(width=640, height=480, fov_h_deg=4.0, fov_v_deg=4.0)
    assert any("Square-pixel" in v for v in exc_info.value.violations)


def test_fps_below_spec() -> None:
    with pytest.raises(ConfigError) as exc_info:
        CameraConfig(fps=20.0)
    assert any("camera.fps" in v for v in exc_info.value.violations)

    # Valid if allow_below_spec_fps is explicitly set
    cam = CameraConfig(fps=20.0, allow_below_spec_fps=True)
    assert cam.fps == 20.0


def test_gimbal_slew_limits() -> None:
    with pytest.raises(ConfigError) as exc_info:
        GimbalConfig(slew_rate_deg_s=11.0, max_slew_rate_deg_s=11.0)
    assert any("Gimbal slew rate" in v for v in exc_info.value.violations)


def test_target_size_spec_limits() -> None:
    with pytest.raises(ConfigError) as exc_info_low:
        TargetConfig(size_px=4)
    assert any("target.size_px" in v for v in exc_info_low.value.violations)

    with pytest.raises(ConfigError) as exc_info_high:
        TargetConfig(size_px=21)
    assert any("target.size_px" in v for v in exc_info_high.value.violations)

    # Allowed if strict_spec is False
    target = TargetConfig(size_px=4, strict_spec=False)
    assert target.size_px == 4


def test_noise_sigma_limit() -> None:
    with pytest.raises(ConfigError) as exc_info:
        DisturbanceConfig(gaussian=GaussianConfig(enabled=True, sigma_levels=25.0))
    assert any("gaussian.sigma_levels" in v for v in exc_info.value.violations)


def test_jitter_and_platform_limits() -> None:
    with pytest.raises(ConfigError) as exc_info:
        DisturbanceConfig(camera_jitter=JitterConfig(enabled=True, max_px_frame=21.0))
    assert any("camera_jitter.max_px_frame" in v for v in exc_info.value.violations)

    with pytest.raises(ConfigError) as exc_info2:
        DisturbanceConfig(platform=PlatformConfig(enabled=True, velocity_px_frame=25.0))
    assert any("platform.velocity_px_frame" in v for v in exc_info2.value.violations)


def test_cross_field_reacquire_timeout() -> None:
    with pytest.raises(ConfigError) as exc_info:
        SkyLockConfig(
            tracking=TrackingConfig(reacquire_timeout_s=1.5),
            requirements=RequirementsConfig(reacquisition_max_s=1.0),
        )
    assert any("tracking.reacquire_timeout_s" in v for v in exc_info.value.violations)


def test_cross_field_deadband_vs_lock_radius() -> None:
    with pytest.raises(ConfigError) as exc_info:
        SkyLockConfig(
            control=ControlConfig(deadband_px=10.0),
            requirements=RequirementsConfig(lock_radius_px=10.0),
        )
    assert any("control.deadband_px" in v for v in exc_info.value.violations)


def test_multi_violation_aggregation() -> None:
    # Test validate_root collects multiple errors without stopping at the first
    cam = CameraConfig(
        width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0, allow_below_spec_fps=True
    )
    with pytest.raises(ConfigError) as exc_info:
        SkyLockConfig(
            camera=cam,
            tracking=TrackingConfig(
                reacquire_timeout_s=2.5,
                acquire_timeout_s=3.0,
            ),
            control=ControlConfig(deadband_px=15.0),
            requirements=RequirementsConfig(
                acquisition_max_s=2.0,
                reacquisition_max_s=1.0,
                lock_radius_px=10.0,
            ),
        )
    violations = exc_info.value.violations
    assert len(violations) >= 3
    violation_text = "\n".join(violations)
    assert "reacquire_timeout_s" in violation_text
    assert "acquire_timeout_s" in violation_text
    assert "deadband_px" in violation_text
