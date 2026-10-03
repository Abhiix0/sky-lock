"""Unit tests for atmospheric degradation models."""

import numpy as np

from skylock.config.models import AtmosphereConfig
from skylock.simulation.disturbances.atmosphere import Atmosphere
from skylock.simulation.disturbances.base import DisturbanceContext


def _create_test_frame() -> np.ndarray:
    """Create a reference synthetic frame with a bright beacon spot on a dark background."""
    img = np.full((120, 160), 20.0, dtype=np.float32)
    # Bright 10x10 beacon spot at center
    img[55:65, 75:85] = 220.0
    return img


def test_atmosphere_contrast_ordering() -> None:
    """Test contrast ordering: contrast(clear) > contrast(haze) > contrast(fog)."""
    base_img = _create_test_frame()
    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)

    clear_model = Atmosphere(AtmosphereConfig(enabled=True, mode="clear", strength=0.5), seed=42)
    haze_model = Atmosphere(AtmosphereConfig(enabled=True, mode="haze", strength=0.5), seed=42)
    fog_model = Atmosphere(AtmosphereConfig(enabled=True, mode="fog", strength=0.5), seed=42)

    img_clear = clear_model.apply(base_img, ctx)
    img_haze = haze_model.apply(base_img, ctx)
    img_fog = fog_model.apply(base_img, ctx)

    contrast_clear = float(np.max(img_clear) - np.min(img_clear))
    contrast_haze = float(np.max(img_haze) - np.min(img_haze))
    contrast_fog = float(np.max(img_fog) - np.min(img_fog))

    assert contrast_clear > contrast_haze, (
        f"Expected contrast(clear) {contrast_clear} > contrast(haze) {contrast_haze}"
    )
    assert contrast_haze > contrast_fog, (
        f"Expected contrast(haze) {contrast_haze} > contrast(fog) {contrast_fog}"
    )


def test_atmosphere_low_light_peak_and_floor() -> None:
    """Test low light peak < clear peak while noise floor / background level is unchanged."""
    base_img = _create_test_frame()
    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)

    ll_model = Atmosphere(
        AtmosphereConfig(enabled=True, mode="low_light", strength=0.7),
        seed=42,
        background_level=20.0,
    )
    img_ll = ll_model.apply(base_img, ctx)

    clear_peak = float(np.max(base_img))
    ll_peak = float(np.max(img_ll))
    ll_bg = float(np.min(img_ll))

    assert ll_peak < clear_peak, f"Expected low_light peak {ll_peak} < clear peak {clear_peak}"
    assert abs(ll_bg - 20.0) < 1e-4, f"Expected background floor 20.0, got {ll_bg}"


def test_atmosphere_rain_streaks() -> None:
    """Test rain mode produces seeded streaks."""
    base_img = _create_test_frame()
    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)

    rain1 = Atmosphere(AtmosphereConfig(enabled=True, mode="rain", strength=0.8), seed=10)
    rain2 = Atmosphere(AtmosphereConfig(enabled=True, mode="rain", strength=0.8), seed=10)

    out1 = rain1.apply(base_img, ctx)
    out2 = rain2.apply(base_img, ctx)

    assert np.array_equal(out1, out2), "Rain streaks should be deterministic with same seed"
    assert not np.array_equal(out1, base_img), "Rain should perturb the image"
