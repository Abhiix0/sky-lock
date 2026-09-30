"""Regression test: visibility_windows are OCCLUSION windows (target hidden while inside).

Bug discovered in Phase 11: S12_occlusion_reacq catalog entry used windows
[[0.0, 2.5], [3.0, 10.0]] thinking they were visibility windows, but the code
treats them as blackout intervals.  Fixed in catalog.py by switching to a single
occlusion gap [[2.5, 3.0]].
"""

from __future__ import annotations

from skylock.config.models import TargetConfig
from skylock.simulation.motion import LineTrajectory
from skylock.simulation.targets import Target, make_sprite


def test_visibility_window_is_occlusion_window() -> None:
    """Target must be HIDDEN while inside a visibility_windows interval."""
    spec = TargetConfig(visibility_windows=((1.0, 2.0),))
    traj = LineTrajectory(start=(0.0, 0.0), speed_deg_s=0.0, heading_deg=0.0)
    sprite = make_sprite("disc", 10)
    target = Target(spec=spec, trajectory=traj, sprite=sprite)

    # Before window: visible
    assert target.is_visible(0.5) is True
    # During window: occluded
    assert target.is_visible(1.0) is False
    assert target.is_visible(1.5) is False
    assert target.is_visible(2.0) is False
    # After window: visible again
    assert target.is_visible(2.5) is True


def test_empty_windows_always_visible() -> None:
    """No windows = always visible."""
    spec = TargetConfig(visibility_windows=())
    traj = LineTrajectory(start=(0.0, 0.0), speed_deg_s=0.0, heading_deg=0.0)
    sprite = make_sprite("disc", 10)
    target = Target(spec=spec, trajectory=traj, sprite=sprite)

    for t in [0.0, 1.0, 10.0, 100.0]:
        assert target.is_visible(t) is True, f"Expected visible at t={t}"


def test_s12_single_gap_window_target_visible_at_start() -> None:
    """S12 occlusion scenario: target must be visible at t=0 and hidden at t=2.75."""
    spec = TargetConfig(visibility_windows=((2.5, 3.0),))
    traj = LineTrajectory(start=(0.0, 0.0), speed_deg_s=0.0, heading_deg=0.0)
    sprite = make_sprite("disc", 10)
    target = Target(spec=spec, trajectory=traj, sprite=sprite)

    # Visible before occlusion
    assert target.is_visible(0.0) is True
    assert target.is_visible(2.4) is True
    # Hidden during occlusion gap
    assert target.is_visible(2.5) is False
    assert target.is_visible(2.75) is False
    assert target.is_visible(3.0) is False
    # Visible again after occlusion
    assert target.is_visible(3.01) is True
    assert target.is_visible(6.0) is True
