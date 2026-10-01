"""Integration test for closed-loop tracking: Simulation -> Pipeline -> Control -> Gimbal."""

from __future__ import annotations

import math

import numpy as np

from skylock.app.session import Session
from skylock.config.models import (
    CameraConfig,
    CircleMotion,
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
from skylock.core.enums import TrackState


def test_closed_loop_line_target_tracking() -> None:
    """Clean scene, line target 0.5 deg/s inside FOV: locks and maintains <= 10 px RMS error."""
    cam = CameraConfig(
        width=640,
        height=480,
        fov_h_deg=4.0,
        fov_v_deg=3.0,
        fps=30.0,
    )
    # Target starts at (0.2, 0.1) deg, moving at 0.5 deg/s on heading 45 deg
    target = TargetConfig(
        initial="fixed",
        initial_pos_deg=(0.2, 0.1),
        motion=LineMotion(speed_deg_s=0.5, heading_deg=45.0),
        size_px=10,
        brightness=220.0,
    )
    cfg = SkyLockConfig(
        camera=cam,
        target=TargetSetConfig(count=1, targets=(target,)),
        gimbal=GimbalConfig(
            initial=(0.0, 0.0),
            slew_rate_deg_s=5.0,
            accel_deg_s2=120.0,
        ),
        detection=DetectionConfig(),
        tracking=TrackingConfig(confirm_hits=3, confirm_window=5),
        control=ControlConfig(
            kp=4.0,
            ki=0.5,
            kd=0.2,
            kff=1.0,
            latency_frames=1,
            deadband_px=0.5,
        ),
        disturbances=DisturbanceConfig(),  # Clean scene
        seed=42,
    )

    session = Session(cfg)

    # Run for 150 frames (5.0 seconds)
    results = session.run(frames=150)
    assert len(results) == 150

    # 1. State must reach TRACK
    states = [res.output.state for res in results]
    assert TrackState.TRACK in states, f"Never reached TRACK state! States visited: {set(states)}"

    first_track_idx = states.index(TrackState.TRACK)
    assert first_track_idx < 30, f"Acquisition took too long: {first_track_idx} frames"

    # Allow 15 frames for control loop to settle after initial lock
    settled_start_idx = first_track_idx + 15
    assert settled_start_idx < len(results)

    # 2. Compute boresight error from GroundTruthSample after settling
    boresight_errors = []
    for res in results[settled_start_idx:]:
        assert res.truth is not None
        if res.truth.boresight_error_px is not None:
            boresight_errors.append(res.truth.boresight_error_px)

    assert len(boresight_errors) > 50
    rms_error = math.sqrt(float(np.mean(np.square(boresight_errors))))
    print(f"\n[Line Closed-Loop] RMS Boresight Error after settling: {rms_error:.2f} px")

    # PS Spec Requirement: tracking error <= 10 px RMS
    assert rms_error <= 10.0, f"RMS boresight error {rms_error:.2f} px exceeds 10.0 px threshold"


def test_closed_loop_circular_target_tracking() -> None:
    """Circular motion target starting inside FOV achieves and maintains closed-loop lock."""
    cam = CameraConfig(
        width=640,
        height=480,
        fov_h_deg=4.0,
        fov_v_deg=3.0,
        fps=30.0,
    )
    # Circle radius 0.6 deg, period 10.0 s -> speed = 2*pi*0.6/10 ~ 0.38 deg/s
    target = TargetConfig(
        initial="fixed",
        initial_pos_deg=(0.0, 0.0),
        motion=CircleMotion(radius_deg=0.6, period_s=10.0, phase_rad=0.0),
        size_px=10,
        brightness=220.0,
    )
    cfg = SkyLockConfig(
        camera=cam,
        target=TargetSetConfig(count=1, targets=(target,)),
        gimbal=GimbalConfig(
            initial=(0.0, 0.0),
            slew_rate_deg_s=5.0,
            accel_deg_s2=120.0,
        ),
        detection=DetectionConfig(),
        tracking=TrackingConfig(confirm_hits=3, confirm_window=5),
        control=ControlConfig(
            kp=4.0,
            ki=0.5,
            kd=0.2,
            kff=1.0,
            latency_frames=1,
            deadband_px=0.5,
        ),
        disturbances=DisturbanceConfig(),
        seed=101,
    )

    session = Session(cfg)
    results = session.run(frames=180)  # 6.0 seconds

    states = [res.output.state for res in results]
    assert TrackState.TRACK in states

    first_track_idx = states.index(TrackState.TRACK)
    settled_start_idx = first_track_idx + 15

    boresight_errors = [
        res.truth.boresight_error_px
        for res in results[settled_start_idx:]
        if res.truth is not None and res.truth.boresight_error_px is not None
    ]

    assert len(boresight_errors) > 50
    rms_error = math.sqrt(float(np.mean(np.square(boresight_errors))))
    print(f"\n[Circle Closed-Loop] RMS Boresight Error after settling: {rms_error:.2f} px")
    assert rms_error <= 10.0, f"RMS boresight error {rms_error:.2f} px exceeds 10.0 px threshold"
