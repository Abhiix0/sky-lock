"""Predefined configuration presets for SkyLock.

Pure functions only — no global or module-level default instances.
"""

from __future__ import annotations

from skylock.config.models import (
    AtmosphereConfig,
    BlurConfig,
    DisturbanceConfig,
    GaussianConfig,
    JitterConfig,
    PlatformConfig,
    PoissonConfig,
    SaltPepperConfig,
    SkyLockConfig,
)


def spec_default() -> SkyLockConfig:
    """Build authoritative PS-spec default SkyLock configuration."""
    return SkyLockConfig()


def preset_clear() -> DisturbanceConfig:
    """Clear atmosphere, zero disturbances."""
    return DisturbanceConfig(
        atmosphere=AtmosphereConfig(enabled=True, mode="clear", strength=0.0)
    )


def preset_haze() -> DisturbanceConfig:
    """Light haze atmosphere preset."""
    return DisturbanceConfig(
        atmosphere=AtmosphereConfig(enabled=True, mode="haze", strength=0.4),
        gaussian=GaussianConfig(enabled=True, sigma_levels=3.0),
    )


def preset_fog() -> DisturbanceConfig:
    """Heavy fog degradation preset."""
    return DisturbanceConfig(
        atmosphere=AtmosphereConfig(enabled=True, mode="fog", strength=0.8),
        blur=BlurConfig(enabled=True, sigma_px=2.0),
        gaussian=GaussianConfig(enabled=True, sigma_levels=6.0),
    )


def preset_rain() -> DisturbanceConfig:
    """Rain disturbance preset with attenuation and streaks."""
    return DisturbanceConfig(
        atmosphere=AtmosphereConfig(enabled=True, mode="rain", strength=0.6),
        salt_pepper=SaltPepperConfig(enabled=True, density=0.01),
        gaussian=GaussianConfig(enabled=True, sigma_levels=5.0),
    )


def preset_low_light() -> DisturbanceConfig:
    """Low-light scenario with Poisson photon noise."""
    return DisturbanceConfig(
        atmosphere=AtmosphereConfig(enabled=True, mode="low_light", strength=0.7),
        poisson=PoissonConfig(enabled=True, photon_scale=0.2),
        gaussian=GaussianConfig(enabled=True, sigma_levels=8.0),
    )


def preset_spec_max_noise() -> DisturbanceConfig:
    """Maximum allowable noise under PS_SPEC §6 (sigma = 20 levels)."""
    return DisturbanceConfig(
        gaussian=GaussianConfig(enabled=True, sigma_levels=20.0),
    )


def preset_spec_max_jitter() -> DisturbanceConfig:
    """Maximum allowable jitter under PS_SPEC §6 (+/-20 px/frame)."""
    return DisturbanceConfig(
        camera_jitter=JitterConfig(enabled=True, max_px_frame=20.0, correlation=0.5),
        platform=PlatformConfig(
            enabled=True, kind="linear", velocity_px_frame=5.0, max_px_frame=20.0
        ),
    )
