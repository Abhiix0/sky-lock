"""Camera jitter disturbance model implementing correlated line-of-sight vibration."""

from __future__ import annotations

import math

import numpy as np

from skylock.config.models import JitterConfig
from skylock.core.rng import derive_rng
from skylock.simulation.disturbances.base import GeometricDisturbance


class CameraJitter(GeometricDisturbance):
    """High-frequency camera pointing jitter with first-order temporal correlation.

    PS_SPEC §6: Camera Jitter up to +/-20 px/frame.
    """

    def __init__(self, config: JitterConfig, seed: int) -> None:
        self.config = config
        self.seed = seed
        self._max_px = min(20.0, max(0.0, float(config.max_px_frame)))
        self._correlation = min(0.9999, max(0.0, float(config.correlation)))
        self._rng: np.random.Generator = derive_rng(seed, "dist.camera_jitter")
        self._history: dict[int, tuple[float, float]] = {}
        self._curr_x: float = 0.0
        self._curr_y: float = 0.0
        self._last_sim_frame: int = -1

    def reset(self) -> None:
        self._rng = derive_rng(self.seed, "dist.camera_jitter")
        self._history.clear()
        self._curr_x = 0.0
        self._curr_y = 0.0
        self._last_sim_frame = -1

    def offset_px(self, frame_index: int, t: float) -> tuple[float, float]:
        if not self.config.enabled or self._max_px <= 0.0:
            return (0.0, 0.0)

        if frame_index in self._history:
            return self._history[frame_index]

        # Advance sequentially up to frame_index to maintain deterministic RNG progression
        rho = self._correlation
        sigma = self._max_px
        innov_scale = math.sqrt(max(0.0, 1.0 - rho * rho)) * sigma

        for f in range(self._last_sim_frame + 1, frame_index + 1):
            if f == 0:
                wx = float(self._rng.standard_normal())
                wy = float(self._rng.standard_normal())
                self._curr_x = sigma * wx
                self._curr_y = sigma * wy
            else:
                wx = float(self._rng.standard_normal())
                wy = float(self._rng.standard_normal())
                self._curr_x = rho * self._curr_x + innov_scale * wx
                self._curr_y = rho * self._curr_y + innov_scale * wy

            # Enforce hard clipping to spec limits: |dx|, |dy| <= max_px_frame
            dx = float(np.clip(self._curr_x, -self._max_px, self._max_px))
            dy = float(np.clip(self._curr_y, -self._max_px, self._max_px))
            self._history[f] = (dx, dy)
            self._last_sim_frame = f

        return self._history[frame_index]
