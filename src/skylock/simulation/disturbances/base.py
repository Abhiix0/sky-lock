"""Base abstract interfaces for physical and optical disturbances."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class DisturbanceContext:
    """Temporal and spatial frame context provided to disturbance operators."""

    frame_index: int
    timestamp_s: float


class Disturbance(ABC):
    """Abstract base class for all resettable disturbance models."""

    @abstractmethod
    def reset(self) -> None:
        """Reset internal state and re-initialize isolated PRNG streams."""


class PhotometricDisturbance(Disturbance, ABC):
    """Disturbance operating directly on the float32 focal-plane image."""

    @abstractmethod
    def apply(self, image: np.ndarray, ctx: DisturbanceContext) -> np.ndarray:
        """Apply photometric corruption to a float32 sensor image [0.0, 255.0].

        Returns:
            Perturbed float32 image array.
        """


class GeometricDisturbance(Disturbance, ABC):
    """Disturbance operating on the optical line-of-sight pointing / pixel offset."""

    @abstractmethod
    def offset_px(self, frame_index: int, t: float) -> tuple[float, float]:
        """Compute pixel displacement (dx, dy) on the sensor plane.

        Returns:
            (dx, dy) in pixels.
        """
