"""Optical defocus and atmospheric point spread function blur disturbance."""

from __future__ import annotations

import cv2
import numpy as np

from skylock.config.models import BlurConfig
from skylock.simulation.disturbances.base import DisturbanceContext, PhotometricDisturbance


class OpticalBlur(PhotometricDisturbance):
    """Optical blur simulating lens defocus and PSF broadening via Gaussian filtering."""

    def __init__(self, config: BlurConfig, seed: int = 0) -> None:
        self.config = config
        self.seed = seed

    def reset(self) -> None:
        pass

    def apply(self, image: np.ndarray, ctx: DisturbanceContext) -> np.ndarray:
        if not self.config.enabled or self.config.sigma_px <= 0.0:
            return image

        sigma = float(self.config.sigma_px)
        return cv2.GaussianBlur(
            image,
            (0, 0),
            sigmaX=sigma,
            sigmaY=sigma,
            borderType=cv2.BORDER_REFLECT,
        )
