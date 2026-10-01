"""Unit tests for configuration presets."""

from skylock.config.models import SkyLockConfig
from skylock.config.presets import (
    preset_clear,
    preset_fog,
    preset_haze,
    preset_low_light,
    preset_rain,
    preset_spec_max_jitter,
    preset_spec_max_noise,
    spec_default,
)


def test_spec_default() -> None:
    cfg = spec_default()
    assert isinstance(cfg, SkyLockConfig)
    assert cfg.camera.fov_h_deg == 4.0
    assert cfg.camera.fov_v_deg == 3.0


def test_disturbance_presets() -> None:
    clear = preset_clear()
    assert clear.atmosphere.enabled is True
    assert clear.atmosphere.mode == "clear"

    haze = preset_haze()
    assert haze.atmosphere.mode == "haze"
    assert haze.gaussian.enabled is True

    fog = preset_fog()
    assert fog.atmosphere.mode == "fog"
    assert fog.blur.enabled is True

    rain = preset_rain()
    assert rain.atmosphere.mode == "rain"
    assert rain.salt_pepper.enabled is True

    low_light = preset_low_light()
    assert low_light.atmosphere.mode == "low_light"
    assert low_light.poisson.enabled is True

    max_noise = preset_spec_max_noise()
    assert max_noise.gaussian.sigma_levels == 20.0

    max_jitter = preset_spec_max_jitter()
    assert max_jitter.camera_jitter.max_px_frame == 20.0
    assert max_jitter.platform.velocity_px_frame == 5.0


def test_presets_return_new_instances() -> None:
    p1 = preset_clear()
    p2 = preset_clear()
    assert p1 is not p2
    assert p1 == p2
