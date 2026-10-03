"""Unit tests for optical blur disturbance model."""

import numpy as np

from skylock.config.models import BlurConfig
from skylock.simulation.disturbances.base import DisturbanceContext
from skylock.simulation.disturbances.blur import OpticalBlur


def test_optical_blur_peak_and_energy() -> None:
    """Test optical blur reduces peak brightness while preserving total energy within 2%."""
    img = np.full((100, 100), 20.0, dtype=np.float32)
    # Bright spot well inside borders to avoid border reflection discrepancies
    img[45:55, 45:55] = 220.0

    orig_peak = float(np.max(img))
    orig_energy = float(np.sum(img))

    blur_model = OpticalBlur(BlurConfig(enabled=True, sigma_px=2.5))
    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)
    blurred = blur_model.apply(img, ctx)

    blurred_peak = float(np.max(blurred))
    blurred_energy = float(np.sum(blurred))

    assert blurred_peak < orig_peak, (
        f"Blur peak {blurred_peak} should be strictly less than original {orig_peak}"
    )

    energy_diff_fraction = abs(blurred_energy - orig_energy) / orig_energy
    assert energy_diff_fraction < 0.02, (
        f"Energy difference fraction {energy_diff_fraction} exceeded 2%"
    )


def test_optical_blur_disabled_noop() -> None:
    """Disabled optical blur returns image unaltered."""
    img = np.full((50, 50), 20.0, dtype=np.float32)
    blur_model = OpticalBlur(BlurConfig(enabled=False, sigma_px=5.0))
    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)
    out = blur_model.apply(img, ctx)
    assert np.array_equal(out, img)
