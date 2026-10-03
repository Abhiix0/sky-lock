"""Unit tests for target sprites, visibility windows, and TargetSet."""

import numpy as np

from skylock.config.models import TargetConfig, TargetSetConfig
from skylock.simulation.motion import LineTrajectory
from skylock.simulation.targets import Target, TargetSet, make_sprite


def test_sprite_generation() -> None:
    size = 10
    sq = make_sprite("square", size)
    assert sq.shape == (10, 10)
    assert np.all(sq == 1.0)

    disc = make_sprite("disc", size)
    assert disc.shape == (10, 10)
    assert disc.max() == 1.0
    # Disc should be symmetric
    assert np.allclose(disc, np.fliplr(disc))
    assert np.allclose(disc, np.flipud(disc))

    gauss = make_sprite("gaussian", size)
    assert gauss.shape == (10, 10)
    assert gauss.max() == 1.0
    assert np.allclose(gauss, np.fliplr(gauss))

    cross = make_sprite("cross", size)
    assert cross.shape == (10, 10)
    assert cross.max() == 1.0

    mask = np.eye(8, dtype=np.float32)
    custom = make_sprite("custom_mask", 8, custom_mask=mask)
    assert custom.shape == (8, 8)
    assert custom.max() == 1.0


def test_visibility_windows() -> None:
    spec = TargetConfig(visibility_windows=((1.0, 2.0), (4.5, 5.0)))
    traj = LineTrajectory(start=(0, 0), speed_deg_s=0.0, heading_deg=0.0)
    sprite = make_sprite("disc", 10)
    target = Target(spec=spec, trajectory=traj, sprite=sprite)

    # Visible before window 1
    assert target.is_visible(0.5) is True
    # Occluded during window 1
    assert target.is_visible(1.0) is False
    assert target.is_visible(1.5) is False
    assert target.is_visible(2.0) is False
    # Visible between windows
    assert target.is_visible(3.0) is True
    # Occluded during window 2
    assert target.is_visible(4.8) is False
    # Visible after window 2
    assert target.is_visible(5.5) is True


def test_target_set_count_three() -> None:
    t1 = TargetConfig(id="t1", initial="fixed", initial_pos_deg=(0.0, 0.0))
    t2 = TargetConfig(id="t2", initial="fixed", initial_pos_deg=(0.5, 0.5))
    t3 = TargetConfig(id="t3", initial="fixed", initial_pos_deg=(-0.5, -0.5))
    cfg = TargetSetConfig(count=3, targets=(t1, t2, t3))

    target_set = TargetSet(cfg, seed=42)
    assert len(target_set.targets) == 3
    assert target_set.targets[0].spec.id == "t1"
    assert target_set.targets[1].spec.id == "t2"
    assert target_set.targets[2].spec.id == "t3"
