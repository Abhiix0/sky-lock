"""Unit tests for sensor photometric noise models (Gaussian, Salt & Pepper, Poisson)."""

import numpy as np

from skylock.config.models import GaussianConfig, PoissonConfig, SaltPepperConfig
from skylock.simulation.disturbances.base import DisturbanceContext
from skylock.simulation.disturbances.noise import (
    GaussianNoise,
    PoissonNoise,
    SaltPepperNoise,
)


def test_gaussian_noise_statistics() -> None:
    """Test Gaussian read noise std dev is within 5% of configured sigma."""
    sigma = 15.0
    config = GaussianConfig(enabled=True, sigma_levels=sigma)
    noise_model = GaussianNoise(config, seed=42)

    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)
    image = np.full((480, 640), 20.0, dtype=np.float32)

    perturbed = noise_model.apply(image, ctx)
    diff = perturbed - image
    measured_sigma = float(np.std(diff))

    rel_error = abs(measured_sigma - sigma) / sigma
    assert rel_error < 0.05, f"Measured sigma {measured_sigma} not within 5% of {sigma}"


def test_salt_pepper_density_fraction() -> None:
    """Test Salt & Pepper extreme fraction (0 or 255) is within 10% of configured density."""
    density = 0.05
    config = SaltPepperConfig(enabled=True, density=density)
    sp_model = SaltPepperNoise(config, seed=123)

    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)
    # Background 20.0 so 0 and 255 are strictly extreme corrupted pixels
    image = np.full((480, 640), 20.0, dtype=np.float32)

    corrupted = sp_model.apply(image, ctx)
    extremes_mask = (corrupted == 0.0) | (corrupted == 255.0)
    measured_fraction = float(np.mean(extremes_mask))

    rel_error = abs(measured_fraction - density) / density
    assert rel_error < 0.10, (
        f"Measured fraction {measured_fraction} not within 10% of density {density}"
    )


def test_poisson_noise_variance() -> None:
    """Test Poisson shot noise variance ~ mean / photon_scale."""
    scale = 0.8
    mean_val = 100.0
    config = PoissonConfig(enabled=True, photon_scale=scale)
    poisson_model = PoissonNoise(config, seed=999)

    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)
    image = np.full((480, 640), mean_val, dtype=np.float32)

    noisy = poisson_model.apply(image, ctx)
    measured_var = float(np.var(noisy))
    expected_var = mean_val / scale

    rel_error = abs(measured_var - expected_var) / expected_var
    assert rel_error < 0.05, (
        f"Measured variance {measured_var} not close to expected {expected_var}"
    )


def test_noise_disabled_noop() -> None:
    """Disabled noise components return image without modifications."""
    img = np.full((100, 100), 20.0, dtype=np.float32)
    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)

    g = GaussianNoise(GaussianConfig(enabled=False, sigma_levels=10.0), seed=1)
    sp = SaltPepperNoise(SaltPepperConfig(enabled=False, density=0.1), seed=2)
    p = PoissonNoise(PoissonConfig(enabled=False, photon_scale=1.0), seed=3)

    assert np.array_equal(g.apply(img, ctx), img)
    assert np.array_equal(sp.apply(img, ctx), img)
    assert np.array_equal(p.apply(img, ctx), img)
