"""Atmospheric degradation disturbance models (Clear, Haze, Fog, Rain, Low-Light)."""

from __future__ import annotations

import math

import cv2
import numpy as np

from skylock.config.models import AtmosphereConfig
from skylock.core.rng import derive_rng
from skylock.simulation.disturbances.base import DisturbanceContext, PhotometricDisturbance


class Atmosphere(PhotometricDisturbance):
    """Atmospheric degradation model operating on optical transmission and contrast.

    PS_SPEC §6: Clear, Haze, Fog, Rain, Low Light.
    """

    def __init__(
        self,
        config: AtmosphereConfig,
        seed: int,
        background_level: float = 20.0,
    ) -> None:
        self.config = config
        self.seed = seed
        self.background_level = float(background_level)
        self._rng: np.random.Generator = derive_rng(seed, "dist.atmosphere")

    def reset(self) -> None:
        self._rng = derive_rng(self.seed, "dist.atmosphere")

    def apply(self, image: np.ndarray, ctx: DisturbanceContext) -> np.ndarray:
        if not self.config.enabled:
            return image

        mode = self.config.mode.lower()
        if mode == "clear":
            return image

        strength = min(1.0, max(0.0, float(self.config.strength)))
        if strength <= 0.0:
            return image

        b = self.background_level

        if mode == "haze":
            # Contrast compression toward background + additive airlight veil
            # Attenuation reduces dynamic range; veil lifts the black level
            signal = image - b
            comp_signal = signal * (1.0 - 0.5 * strength)
            veil = 30.0 * strength
            return b + comp_signal + veil

        if mode == "fog":
            # Stronger veil + heavier attenuation + optical scattering blur
            signal = image - b
            att_signal = signal * (1.0 - 0.85 * strength)
            veil = 60.0 * strength
            base = b + att_signal + veil
            # Atmospheric blur sigma ~ 1.0 px
            sigma = 1.0 * max(0.5, strength)
            return cv2.GaussianBlur(
                base, (0, 0), sigmaX=sigma, sigmaY=sigma, borderType=cv2.BORDER_REFLECT
            )

        if mode == "rain":
            # Seeded streaks + mild atmospheric attenuation
            signal = image - b
            out = b + signal * (1.0 - 0.15 * strength)
            # Draw semi-transparent rain streaks using deterministic RNG
            num_streaks = int(40 * strength)
            h, w = out.shape[:2]
            streak_color = float(b + 35.0 * strength)
            for _ in range(num_streaks):
                x0 = int(self._rng.integers(0, w))
                y0 = int(self._rng.integers(0, h))
                length = float(self._rng.uniform(10.0, 25.0))
                # Rain falls downward with slight angular slant (~75 degrees)
                x1 = int(x0 + length * math.cos(math.radians(75.0)))
                y1 = int(y0 + length * math.sin(math.radians(75.0)))
                cv2.line(out, (x0, y0), (x1, y1), streak_color, 1)
            return out

        if mode == "low_light":
            # Signal gain g < 1.0 while maintaining the sensor noise floor / background level
            gain = 1.0 - 0.75 * strength
            signal = np.maximum(0.0, image - b)
            return b + gain * signal

        return image
