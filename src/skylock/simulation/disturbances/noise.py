"""Photometric sensor noise disturbance models (Salt & Pepper, Gaussian, Poisson)."""

from __future__ import annotations

import numpy as np

from skylock.config.models import GaussianConfig, PoissonConfig, SaltPepperConfig
from skylock.core.rng import derive_rng
from skylock.simulation.disturbances.base import DisturbanceContext, PhotometricDisturbance


class SaltPepperNoise(PhotometricDisturbance):
    """Impulse noise simulating saturated salt (255) and dead pepper (0) pixels."""

    def __init__(self, config: SaltPepperConfig, seed: int) -> None:
        self.config = config
        self.seed = seed
        self._rng: np.random.Generator = derive_rng(seed, "dist.salt_pepper")

    def reset(self) -> None:
        self._rng = derive_rng(self.seed, "dist.salt_pepper")

    def apply(self, image: np.ndarray, ctx: DisturbanceContext) -> np.ndarray:
        if not self.config.enabled or self.config.density <= 0.0:
            return image

        density = min(1.0, max(0.0, float(self.config.density)))
        u = self._rng.uniform(0.0, 1.0, size=image.shape).astype(np.float32)

        out = image.copy()
        # Half of corrupted pixels are pepper (0), half are salt (255)
        pepper_mask = u < (density * 0.5)
        salt_mask = (u >= (density * 0.5)) & (u < density)

        out[pepper_mask] = 0.0
        out[salt_mask] = 255.0
        return out


class GaussianNoise(PhotometricDisturbance):
    """Sensor read noise modeling Gaussian thermal/amplifier noise on focal plane."""

    def __init__(self, config: GaussianConfig, seed: int) -> None:
        self.config = config
        self.seed = seed
        self._rng: np.random.Generator = derive_rng(seed, "dist.gaussian")

    def reset(self) -> None:
        self._rng = derive_rng(self.seed, "dist.gaussian")

    def apply(self, image: np.ndarray, ctx: DisturbanceContext) -> np.ndarray:
        if not self.config.enabled or self.config.sigma_levels <= 0.0:
            return image

        # PS_SPEC §6: maximum allowable standard deviation is 20 grey levels
        sigma = min(20.0, max(0.0, float(self.config.sigma_levels)))
        noise = self._rng.normal(0.0, sigma, size=image.shape).astype(np.float32)
        return image + noise


class PoissonNoise(PhotometricDisturbance):
    """Shot noise modeling quantum photon arrival statistics on the sensor.

    For photon expectation lambda > 50, a Gaussian normal approximation
    N(lambda, lambda) is used to ensure execution time <= 6 ms at 640x480.
    """

    def __init__(
        self,
        config: PoissonConfig,
        seed: int,
        normal_approx_threshold: float = 50.0,
    ) -> None:
        self.config = config
        self.seed = seed
        self.normal_approx_threshold = normal_approx_threshold
        self._rng: np.random.Generator = derive_rng(seed, "dist.poisson")

    def reset(self) -> None:
        self._rng = derive_rng(self.seed, "dist.poisson")

    def apply(self, image: np.ndarray, ctx: DisturbanceContext) -> np.ndarray:
        if not self.config.enabled or self.config.photon_scale <= 0.0:
            return image

        scale = float(self.config.photon_scale)
        lam = np.maximum(image * scale, 0.0)

        thresh = self.normal_approx_threshold
        min_lam = float(np.min(lam))
        max_lam = float(np.max(lam))

        if min_lam > thresh:
            # Fast vectorized normal approximation: Poisson(lambda) ~ N(lambda, lambda)
            noise = self._rng.standard_normal(lam.shape, dtype=np.float32)
            photons = lam + np.sqrt(lam) * noise
        elif max_lam <= thresh:
            # Exact Poisson draw
            photons = self._rng.poisson(lam).astype(np.float32)
        else:
            # Hybrid: normal approximation for high counts, exact for low counts
            photons = np.empty_like(lam, dtype=np.float32)
            mask = lam > thresh
            count_large = int(np.count_nonzero(mask))
            if count_large > 0:
                noise_large = self._rng.standard_normal(count_large, dtype=np.float32)
                photons[mask] = lam[mask] + np.sqrt(lam[mask]) * noise_large
            photons[~mask] = self._rng.poisson(lam[~mask]).astype(np.float32)

        return photons / scale
