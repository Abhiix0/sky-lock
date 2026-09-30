"""Platform motion disturbance model simulating terminal mounting drift and translation."""

from __future__ import annotations

import math

import numpy as np

from skylock.config.models import PlatformConfig
from skylock.core.rng import derive_rng
from skylock.simulation.disturbances.base import GeometricDisturbance


class PlatformMotion(GeometricDisturbance):
    """Platform motion disturbance accumulating drift across frames.

    PS_SPEC §6: Platform motion up to +/-20 px/frame (linear motion mandatory).
    """

    def __init__(self, config: PlatformConfig, seed: int) -> None:
        self.config = config
        self.seed = seed
        self._rng: np.random.Generator = derive_rng(seed, "dist.platform")

        v_raw = config.velocity_px_frame
        if isinstance(v_raw, (int, float)):
            vx, vy = float(v_raw), 0.0
        else:
            vx, vy = float(v_raw[0]), float(v_raw[1])

        v_mag = math.hypot(vx, vy)
        max_limit = 20.0
        if config.max_px_frame > 0.0:
            max_limit = min(20.0, float(config.max_px_frame))

        if v_mag > max_limit and v_mag > 0.0:
            scale = max_limit / v_mag
            self._vx_eff = vx * scale
            self._vy_eff = vy * scale
        else:
            self._vx_eff = vx
            self._vy_eff = vy

    def reset(self) -> None:
        self._rng = derive_rng(self.seed, "dist.platform")

    def offset_px(self, frame_index: int, t: float) -> tuple[float, float]:
        if not self.config.enabled:
            return (0.0, 0.0)

        if self.config.kind == "sinusoidal":
            # Sinusoidal motion bounded by max_limit
            omega = 2.0 * math.pi * 0.5
            dx = self._vx_eff * math.sin(omega * t)
            dy = self._vy_eff * math.cos(omega * t)
            return (dx, dy)

        # Default / mandatory "linear" kinematics: constant velocity accumulating per frame
        dx = float(frame_index) * self._vx_eff
        dy = float(frame_index) * self._vy_eff
        return (dx, dy)
