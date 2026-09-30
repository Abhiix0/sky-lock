"""Unit tests for VirtualCamera rendering, projection, and sub-pixel splatting accuracy."""

import numpy as np
import pytest

from skylock.config.models import CameraConfig, TargetConfig
from skylock.core.geometry import pixel_to_angle_offset
from skylock.core.types import Pointing
from skylock.simulation.camera import VirtualCamera
from skylock.simulation.motion import LineTrajectory
from skylock.simulation.targets import Target, make_sprite


def _compute_centroid(image: np.ndarray, bg_level: float) -> tuple[float, float]:
    """Compute intensity-weighted sub-pixel centroid after background subtraction."""
    fg = np.maximum(0.0, image - bg_level)
    total_mass = float(np.sum(fg))
    if total_mass == 0.0:
        return (0.0, 0.0)

    y_indices, x_indices = np.indices(image.shape, dtype=np.float32)
    cx = float(np.sum(fg * x_indices) / total_mass)
    cy = float(np.sum(fg * y_indices) / total_mass)
    return (cx, cy)


def test_subpixel_splat_centroid_accuracy() -> None:
    cam_cfg = CameraConfig(
        width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0, background_level=20.0
    )
    camera = VirtualCamera(cam_cfg)

    # Position target at fractional pixel coordinates near sensor center
    target_px, target_py = 325.35, 238.65
    dpan, dtilt = pixel_to_angle_offset(target_px, target_py, cam_cfg)

    traj = LineTrajectory(start=(dpan, dtilt), speed_deg_s=0.0, heading_deg=0.0)
    sprite = make_sprite("disc", 10)
    target = Target(
        spec=TargetConfig(size_px=10, brightness=200.0), trajectory=traj, sprite=sprite
    )

    pointing = Pointing(0.0, 0.0)
    image, infos = camera.render(pointing=pointing, t=0.0, targets=[target])

    assert len(infos) == 1
    assert infos[0].in_fov is True
    assert infos[0].px == pytest.approx(target_px, abs=1e-5)
    assert infos[0].py == pytest.approx(target_py, abs=1e-5)

    # Compute intensity-weighted centroid in image
    meas_cx, meas_cy = _compute_centroid(image, bg_level=cam_cfg.background_level)

    # Centroid must match ground truth to within 0.1 px (plan requirement)
    assert meas_cx == pytest.approx(target_px, abs=0.05)
    assert meas_cy == pytest.approx(target_py, abs=0.05)


def test_target_outside_fov_renders_blank_frame() -> None:
    cam_cfg = CameraConfig(
        width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0, background_level=20.0
    )
    camera = VirtualCamera(cam_cfg)

    # Target placed far outside FOV (10 degrees away)
    traj = LineTrajectory(start=(10.0, 10.0), speed_deg_s=0.0, heading_deg=0.0)
    sprite = make_sprite("disc", 10)
    target = Target(spec=TargetConfig(size_px=10), trajectory=traj, sprite=sprite)

    image, infos = camera.render(pointing=Pointing(0.0, 0.0), t=0.0, targets=[target])

    assert infos[0].in_fov is False
    # Entire image must remain at uniform background level
    assert np.all(image == cam_cfg.background_level)
