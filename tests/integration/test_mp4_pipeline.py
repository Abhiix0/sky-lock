"""Integration test verifying Mp4Source through Session and TrackingPipeline."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

try:
    from scripts.gen_test_video import generate_test_video  # type: ignore
except (ImportError, ModuleNotFoundError):
    import sys

    _root = Path(__file__).resolve().parents[2]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from scripts.gen_test_video import generate_test_video  # type: ignore

from skylock.app.session import Session
from skylock.config.models import (
    DetectionConfig,
    DisturbanceConfig,
    InputConfig,
    SkyLockConfig,
    TrackingConfig,
)
from skylock.core.enums import TrackState
from skylock.core.pipeline import TrackingPipeline


def test_mp4_session_and_pipeline_equivalence(tmp_path: Path) -> None:
    """MP4 video decoded via Session reaches TRACK and matches direct TrackingPipeline output."""
    video_path = tmp_path / "test_track_scene.mp4"

    try:
        generate_test_video(video_path, seconds=2.5, seed=42)
    except RuntimeError as exc:
        pytest.skip(f"Skipping MP4 integration test: VideoWriter codec error ({exc})")

    # Configure SkyLock with MP4 input
    cfg = SkyLockConfig(
        input=InputConfig(kind="mp4", mp4_path=str(video_path), mp4_assumed_fov_h_deg=4.0),
        detection=DetectionConfig(),
        tracking=TrackingConfig(confirm_hits=3, confirm_window=5),
        disturbances=DisturbanceConfig(),
    )

    # 1. Run through Session
    session = Session(cfg)
    session_results = session.run()

    assert len(session_results) > 30, f"Decoded only {len(session_results)} frames"

    # Verify tracker reaches TRACK on the beacon video
    states = [res.output.state for res in session_results]
    assert TrackState.TRACK in states, f"Tracker never reached TRACK on MP4! States: {set(states)}"

    # Verify ground-truth firewall: MP4 source produces no truth
    assert all(res.truth is None for res in session_results), (
        "Ground truth leaked into MP4 StepResult"
    )

    # 2. Run directly through TrackingPipeline on the same decoded frames
    # Derive matching effective camera configuration
    w = session.source.width
    h = session.source.height
    fov_h = cfg.input.mp4_assumed_fov_h_deg
    fov_v = fov_h * (float(h) / float(w))

    effective_camera = replace(
        cfg.camera,
        width=w,
        height=h,
        fov_h_deg=fov_h,
        fov_v_deg=fov_v,
        fps=session.source.fps,
        allow_below_spec_fps=True,
    )
    direct_pipeline = TrackingPipeline(replace(cfg, camera=effective_camera))

    direct_outputs = [direct_pipeline.process(res.frame) for res in session_results]

    assert len(direct_outputs) == len(session_results)

    # 3. Assert step-by-step equality of pipeline outputs
    for i, (res, direct_out) in enumerate(zip(session_results, direct_outputs, strict=True)):
        out = res.output
        assert out.state == direct_out.state, (
            f"Frame {i}: state mismatch ({out.state} vs {direct_out.state})"
        )
        assert out.intent.mode == direct_out.intent.mode
        if out.intent.image_error_px is not None:
            assert direct_out.intent.image_error_px is not None
            assert out.intent.image_error_px == direct_out.intent.image_error_px
        else:
            assert direct_out.intent.image_error_px is None

        if out.estimate is not None:
            assert direct_out.estimate is not None
            assert out.estimate.px == direct_out.estimate.px
            assert out.estimate.py == direct_out.estimate.py
            assert out.estimate.pan_deg == direct_out.estimate.pan_deg
            assert out.estimate.tilt_deg == direct_out.estimate.tilt_deg
        else:
            assert direct_out.estimate is None
