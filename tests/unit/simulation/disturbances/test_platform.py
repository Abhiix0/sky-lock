"""Unit tests for platform motion disturbance model."""

import pytest

from skylock.config.models import PlatformConfig
from skylock.simulation.disturbances.platform import PlatformMotion


def test_platform_linear_drift() -> None:
    """Test linear platform motion accumulates velocity exactly per frame."""
    vx, vy = 2.5, -1.0
    config = PlatformConfig(enabled=True, kind="linear", velocity_px_frame=(vx, vy))
    plat = PlatformMotion(config, seed=1)

    for f in range(20):
        t = f / 30.0
        dx, dy = plat.offset_px(f, t)
        expected_dx = f * vx
        expected_dy = f * vy
        assert dx == pytest.approx(expected_dx)
        assert dy == pytest.approx(expected_dy)


def test_platform_velocity_clipping() -> None:
    """Test platform velocity is clipped when exceeding max limit (PS_SPEC <= 20)."""
    # Exceeding configured max_px_frame: 25 px/frame with limit 15
    config = PlatformConfig(
        enabled=True, kind="linear", velocity_px_frame=(25.0, 0.0), max_px_frame=15.0
    )
    plat = PlatformMotion(config, seed=1)

    for f in range(10):
        dx, dy = plat.offset_px(f, f / 30.0)
        assert dx == pytest.approx(f * 15.0)
        assert dy == pytest.approx(0.0)


def test_platform_disabled_returns_zero() -> None:
    """Disabled platform motion returns (0.0, 0.0)."""
    config = PlatformConfig(enabled=False, velocity_px_frame=(5.0, 5.0))
    plat = PlatformMotion(config, seed=1)
    assert plat.offset_px(10, 1.0) == (0.0, 0.0)
