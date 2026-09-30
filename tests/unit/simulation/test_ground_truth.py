"""Unit tests for ground truth telemetry construction."""

import pytest

from skylock.config.models import CameraConfig, TargetConfig
from skylock.core.types import Pointing
from skylock.simulation.camera import VirtualCamera
from skylock.simulation.ground_truth import build_ground_truth
from skylock.simulation.motion import LineTrajectory
from skylock.simulation.targets import Target, make_sprite


def test_ground_truth_in_fov_visible() -> None:
    cam_cfg = CameraConfig(width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0)
    camera = VirtualCamera(cam_cfg)

    # Position at (0, 0) az, el -> center pixel
    traj = LineTrajectory(start=(0.0, 0.0), speed_deg_s=0.0, heading_deg=0.0)
    sprite = make_sprite("disc", 10)
    target = Target(spec=TargetConfig(id="beacon_0"), trajectory=traj, sprite=sprite)

    pointing = Pointing(0.0, 0.0)
    _, render_infos = camera.render(pointing, t=0.0, targets=[target])

    gt = build_ground_truth(
        frame_index=0,
        timestamp_s=0.0,
        render_infos=render_infos,
        targets=[target],
        pointing=pointing,
        camera=cam_cfg,
    )

    assert gt.primary_visible is True
    assert gt.primary_px is not None
    assert gt.primary_px[0] == pytest.approx(319.5, abs=0.5)
    assert gt.primary_px[1] == pytest.approx(239.5, abs=0.5)
    assert gt.boresight_error_px is not None
    assert gt.boresight_error_px == pytest.approx(0.0, abs=1e-5)


def test_ground_truth_outside_fov() -> None:
    cam_cfg = CameraConfig(width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0)
    camera = VirtualCamera(cam_cfg)

    # Target 5 degrees away -> outside FOV
    traj = LineTrajectory(start=(5.0, 5.0), speed_deg_s=0.0, heading_deg=0.0)
    sprite = make_sprite("disc", 10)
    target = Target(spec=TargetConfig(id="beacon_0"), trajectory=traj, sprite=sprite)

    pointing = Pointing(0.0, 0.0)
    _, render_infos = camera.render(pointing, t=0.0, targets=[target])

    gt = build_ground_truth(
        frame_index=1,
        timestamp_s=0.033,
        render_infos=render_infos,
        targets=[target],
        pointing=pointing,
        camera=cam_cfg,
    )

    assert gt.primary_visible is False
    assert gt.primary_px is None


def test_ground_truth_visibility_window_blanks() -> None:
    cam_cfg = CameraConfig(width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0)
    camera = VirtualCamera(cam_cfg)

    # In FOV but occluded at t=1.0
    traj = LineTrajectory(start=(0.0, 0.0), speed_deg_s=0.0, heading_deg=0.0)
    sprite = make_sprite("disc", 10)
    target = Target(
        spec=TargetConfig(id="beacon_0", visibility_windows=((0.5, 1.5),)),
        trajectory=traj,
        sprite=sprite,
    )

    pointing = Pointing(0.0, 0.0)
    _, render_infos = camera.render(pointing, t=1.0, targets=[target])

    gt = build_ground_truth(
        frame_index=30,
        timestamp_s=1.0,
        render_infos=render_infos,
        targets=[target],
        pointing=pointing,
        camera=cam_cfg,
    )

    assert gt.primary_visible is False
    assert gt.primary_px is None
