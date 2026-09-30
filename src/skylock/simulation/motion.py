"""Kinematic motion models and trajectory generators for simulated targets."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from skylock.core.rng import derive_rng


class Trajectory(ABC):
    """Abstract base class for target angular trajectories."""

    @abstractmethod
    def position(self, t: float) -> tuple[float, float]:
        """Compute target angular position (az_deg, el_deg) at time t (seconds)."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset trajectory internal state / generator."""
        ...


class LineTrajectory(Trajectory):
    """Straight-line trajectory with constant velocity."""

    def __init__(
        self,
        start: tuple[float, float],
        speed_deg_s: float,
        heading_deg: float,
    ) -> None:
        self.start = start
        self.speed_deg_s = speed_deg_s
        self.heading_deg = heading_deg
        rad = math.radians(heading_deg)
        self._vx = speed_deg_s * math.cos(rad)
        self._vy = speed_deg_s * math.sin(rad)

    def position(self, t: float) -> tuple[float, float]:
        az = self.start[0] + self._vx * t
        el = self.start[1] + self._vy * t
        return (az, el)

    def reset(self) -> None:
        pass


class CircleTrajectory(Trajectory):
    """Circular trajectory with constant radius and period."""

    def __init__(
        self,
        center: tuple[float, float],
        radius_deg: float,
        period_s: float,
        phase_rad: float = 0.0,
    ) -> None:
        self.center = center
        self.radius_deg = radius_deg
        self.period_s = period_s
        self.phase_rad = phase_rad
        self._omega = 2.0 * math.pi / period_s

    def position(self, t: float) -> tuple[float, float]:
        angle = self._omega * t + self.phase_rad
        az = self.center[0] + self.radius_deg * math.cos(angle)
        el = self.center[1] + self.radius_deg * math.sin(angle)
        return (az, el)

    def reset(self) -> None:
        pass


class Figure8Trajectory(Trajectory):
    """Figure-8 (Lemniscate of Gerono) trajectory.

    Crosses the centre at t=0 and completes each closed cycle in period_s.
    """

    def __init__(
        self,
        center: tuple[float, float],
        width_deg: float,
        height_deg: float,
        period_s: float,
    ) -> None:
        self.center = center
        self.width_deg = width_deg
        self.height_deg = height_deg
        self.period_s = period_s
        self._omega = 2.0 * math.pi / period_s

    def position(self, t: float) -> tuple[float, float]:
        wt = self._omega * t
        az = self.center[0] + self.width_deg * math.sin(wt)
        el = self.center[1] + self.height_deg * math.sin(wt) * math.cos(wt)
        return (az, el)

    def reset(self) -> None:
        pass


class RandomTrajectory(Trajectory):
    """Random walk trajectory via Ornstein-Uhlenbeck velocity with boundary reflection.

    Evaluated lazily on a fixed 1/120s grid and cached for deterministic results.
    """

    DT_GRID: float = 1.0 / 120.0

    def __init__(
        self,
        start: tuple[float, float],
        speed_deg_s: float,
        correlation_s: float,
        bounds_deg: tuple[float, float, float, float],
        seed: int,
        target_index: int = 0,
    ) -> None:
        self.start = start
        self.speed_deg_s = speed_deg_s
        self.correlation_s = max(1e-4, correlation_s)
        self.bounds_deg = bounds_deg
        self.seed = seed
        self.target_index = target_index

        self._history_pos: list[tuple[float, float]] = []
        self._history_vel: list[tuple[float, float]] = []
        self._rng = derive_rng(seed, f"motion.{target_index}")
        self._init_history()

    def _init_history(self) -> None:
        self._history_pos = [self.start]
        # Initial stationary velocity sample
        w = self._rng.standard_normal(2)
        v0 = (float(w[0] * self.speed_deg_s), float(w[1] * self.speed_deg_s))
        self._history_vel = [v0]

    def _step_until(self, step_index: int) -> None:
        dt = self.DT_GRID
        tau = self.correlation_s
        decay = math.exp(-dt / tau)
        noise_std = self.speed_deg_s * math.sqrt(max(0.0, 1.0 - decay * decay))
        min_az, max_az, min_el, max_el = self.bounds_deg

        while len(self._history_pos) <= step_index:
            cur_p = self._history_pos[-1]
            cur_v = self._history_vel[-1]

            w = self._rng.standard_normal(2)
            next_vx = cur_v[0] * decay + noise_std * float(w[0])
            next_vy = cur_v[1] * decay + noise_std * float(w[1])

            next_px = cur_p[0] + next_vx * dt
            next_py = cur_p[1] + next_vy * dt

            # Azimuth boundary reflection
            if next_px < min_az:
                next_px = 2.0 * min_az - next_px
                next_vx = -next_vx
            elif next_px > max_az:
                next_px = 2.0 * max_az - next_px
                next_vx = -next_vx
            next_px = max(min_az, min(max_az, next_px))

            # Elevation boundary reflection
            if next_py < min_el:
                next_py = 2.0 * min_el - next_py
                next_vy = -next_vy
            elif next_py > max_el:
                next_py = 2.0 * max_el - next_py
                next_vy = -next_vy
            next_py = max(min_el, min(max_el, next_py))

            self._history_pos.append((next_px, next_py))
            self._history_vel.append((next_vx, next_vy))

    def position(self, t: float) -> tuple[float, float]:
        if t < 0.0:
            return self.start

        k = int(math.floor(t / self.DT_GRID))
        self._step_until(k + 1)

        p0 = self._history_pos[k]
        p1 = self._history_pos[k + 1]
        frac = (t - k * self.DT_GRID) / self.DT_GRID
        az = p0[0] + frac * (p1[0] - p0[0])
        el = p0[1] + frac * (p1[1] - p0[1])
        return (az, el)

    def reset(self) -> None:
        self._rng = derive_rng(self.seed, f"motion.{self.target_index}")
        self._init_history()
