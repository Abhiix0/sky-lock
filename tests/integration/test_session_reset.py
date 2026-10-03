"""Integration test verifying exact bit-level determinism of Session across reset()."""

from __future__ import annotations

import pytest

from skylock.app.session import Session
from skylock.config.models import (
    CameraConfig,
    ControlConfig,
    DetectionConfig,
    DisturbanceConfig,
    GimbalConfig,
    LineMotion,
    SkyLockConfig,
    TargetConfig,
    TargetSetConfig,
    TrackingConfig,
)


def test_session_reset_determinism() -> None:
    """Running 200 frames, resetting, and rerunning yields identical PipelineOutput sequence."""
    cam = CameraConfig(
        width=640,
        height=480,
        fov_h_deg=4.0,
        fov_v_deg=3.0,
        fps=30.0,
    )
    target = TargetConfig(
        initial="fixed",
        initial_pos_deg=(0.1, -0.1),
        motion=LineMotion(speed_deg_s=0.3, heading_deg=30.0),
        size_px=10,
        brightness=220.0,
    )
    cfg = SkyLockConfig(
        camera=cam,
        target=TargetSetConfig(count=1, targets=(target,)),
        gimbal=GimbalConfig(initial=(0.0, 0.0), slew_rate_deg_s=5.0),
        detection=DetectionConfig(),
        tracking=TrackingConfig(),
        control=ControlConfig(latency_frames=1),
        disturbances=DisturbanceConfig(),
        seed=98765,
    )

    session = Session(cfg)

    # First run of 200 frames
    run1 = session.run(frames=200)
    assert len(run1) == 200

    # Reset session completely
    session.reset()

    # Second run of 200 frames
    run2 = session.run(frames=200)
    assert len(run2) == 200

    # Compare step by step
    for i in range(200):
        out1 = run1[i].output
        out2 = run2[i].output

        # Compare frame metadata
        assert run1[i].frame.index == run2[i].frame.index
        assert run1[i].frame.timestamp_s == run2[i].frame.timestamp_s

        # Pointing telemetry
        p1 = run1[i].frame.pointing
        p2 = run2[i].frame.pointing
        assert p1 is not None and p2 is not None
        assert p1.pan_deg == pytest.approx(p2.pan_deg, abs=1e-12)
        assert p1.tilt_deg == pytest.approx(p2.tilt_deg, abs=1e-12)

        # Pipeline outputs
        assert out1.state == out2.state, f"Frame {i}: states differ ({out1.state} vs {out2.state})"
        assert out1.intent.mode == out2.intent.mode

        if out1.intent.image_error_px is not None:
            assert out2.intent.image_error_px is not None
            assert out1.intent.image_error_px[0] == pytest.approx(
                out2.intent.image_error_px[0], abs=1e-10
            )
            assert out1.intent.image_error_px[1] == pytest.approx(
                out2.intent.image_error_px[1], abs=1e-10
            )
        else:
            assert out2.intent.image_error_px is None

        if out1.estimate is not None:
            assert out2.estimate is not None
            assert out1.estimate.pan_deg == pytest.approx(out2.estimate.pan_deg, abs=1e-10)
            assert out1.estimate.tilt_deg == pytest.approx(out2.estimate.tilt_deg, abs=1e-10)
            assert out1.estimate.pan_rate == pytest.approx(
                out2.estimate.pan_rate, abs=1e-10
            )
            assert out1.estimate.tilt_rate == pytest.approx(
                out2.estimate.tilt_rate, abs=1e-10
            )
            assert out1.estimate.px == pytest.approx(out2.estimate.px, abs=1e-10)
            assert out1.estimate.py == pytest.approx(out2.estimate.py, abs=1e-10)
        else:
            assert out2.estimate is None

        # Control commands
        cmd1 = run1[i].command
        cmd2 = run2[i].command
        assert cmd1.pan_rate_deg_s == pytest.approx(cmd2.pan_rate_deg_s, abs=1e-10)
        assert cmd1.tilt_rate_deg_s == pytest.approx(cmd2.tilt_rate_deg_s, abs=1e-10)
