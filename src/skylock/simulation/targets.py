"""Target optical beacon specifications, shape generation, and visibility handling."""

from __future__ import annotations

import numpy as np

from skylock.config.models import (
    CircleMotion,
    Figure8Motion,
    LineMotion,
    RandomMotion,
    TargetConfig,
    TargetSetConfig,
)
from skylock.core.rng import derive_rng
from skylock.simulation.motion import (
    CircleTrajectory,
    Figure8Trajectory,
    LineTrajectory,
    RandomTrajectory,
    Trajectory,
)


def make_sprite(shape: str, size_px: int, custom_mask: np.ndarray | None = None) -> np.ndarray:
    """Generate a 2-D float32 target spot sprite in [0.0, 1.0]."""
    size_px = max(1, size_px)
    cx = (size_px - 1.0) / 2.0
    cy = (size_px - 1.0) / 2.0

    y_indices, x_indices = np.indices((size_px, size_px), dtype=np.float32)

    if shape == "square":
        return np.ones((size_px, size_px), dtype=np.float32)

    if shape == "disc":
        radius = size_px / 2.0
        dist_sq = (x_indices - cx) ** 2 + (y_indices - cy) ** 2
        disc = (dist_sq <= (radius**2)).astype(np.float32)
        if disc.max() == 0.0:
            disc[round(cy), round(cx)] = 1.0
        return disc

    if shape == "gaussian":
        sigma = max(0.5, size_px / 4.0)
        dist_sq = (x_indices - cx) ** 2 + (y_indices - cy) ** 2
        gauss = np.exp(-dist_sq / (2.0 * sigma**2)).astype(np.float32)
        peak = float(gauss.max())
        if peak > 0:
            gauss /= peak
        return gauss

    if shape == "cross":
        thickness = max(1, size_px // 3)
        half_th = thickness / 2.0
        cross = np.zeros((size_px, size_px), dtype=np.float32)
        cross[np.abs(y_indices - cy) <= half_th] = 1.0
        cross[np.abs(x_indices - cx) <= half_th] = 1.0
        return cross

    if shape == "custom_mask":
        if custom_mask is not None:
            m = custom_mask.astype(np.float32)
            peak = float(m.max())
            if peak > 0:
                m /= peak
            return m
        return np.ones((size_px, size_px), dtype=np.float32)

    return np.ones((size_px, size_px), dtype=np.float32)


class Target:
    """Individual optical beacon target instance."""

    def __init__(
        self,
        spec: TargetConfig,
        trajectory: Trajectory,
        sprite: np.ndarray,
    ) -> None:
        self.spec = spec
        self.trajectory = trajectory
        self.sprite = sprite
        self.brightness = spec.brightness
        self.visibility_windows = spec.visibility_windows

    def position(self, t: float) -> tuple[float, float]:
        return self.trajectory.position(t)

    def is_visible(self, t: float) -> bool:
        return all(not (t0 <= t <= t1) for t0, t1 in self.visibility_windows)

    def reset(self) -> None:
        self.trajectory.reset()


class TargetSet:
    """Collection of targets parameterized by TargetSetConfig and root seed."""

    def __init__(self, config: TargetSetConfig, seed: int) -> None:
        self.config = config
        self.seed = seed
        self.targets: list[Target] = []
        self._init_targets()

    def _init_targets(self) -> None:
        init_rng = derive_rng(self.seed, "target.initial")

        self.targets.clear()
        for idx, t_cfg in enumerate(self.config.targets):
            if t_cfg.initial == "random":
                az = float(init_rng.uniform(-1.0, 1.0))
                el = float(init_rng.uniform(-0.75, 0.75))
                start = (az, el)
            else:
                start = t_cfg.initial_pos_deg

            motion = t_cfg.motion
            if isinstance(motion, LineMotion):
                traj: Trajectory = LineTrajectory(
                    start=start,
                    speed_deg_s=motion.speed_deg_s,
                    heading_deg=motion.heading_deg,
                )
            elif isinstance(motion, CircleMotion):
                traj = CircleTrajectory(
                    center=start,
                    radius_deg=motion.radius_deg,
                    period_s=motion.period_s,
                    phase_rad=motion.phase_rad,
                )
            elif isinstance(motion, Figure8Motion):
                traj = Figure8Trajectory(
                    center=start,
                    width_deg=motion.width_deg,
                    height_deg=motion.height_deg,
                    period_s=motion.period_s,
                )
            elif isinstance(motion, RandomMotion):
                traj = RandomTrajectory(
                    start=start,
                    speed_deg_s=motion.speed_deg_s,
                    correlation_s=motion.correlation_s,
                    bounds_deg=motion.bounds_deg,
                    seed=self.seed,
                    target_index=idx,
                )
            else:
                traj = LineTrajectory(start=start, speed_deg_s=0.5, heading_deg=0.0)

            sprite = make_sprite(t_cfg.shape, t_cfg.size_px)
            target = Target(spec=t_cfg, trajectory=traj, sprite=sprite)
            self.targets.append(target)

    def reset(self) -> None:
        self._init_targets()
        for t in self.targets:
            t.reset()
