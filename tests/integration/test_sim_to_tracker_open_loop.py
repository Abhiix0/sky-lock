"""Integration test for SimulationSource connected open-loop to TrackingPipeline."""

from __future__ import annotations

from skylock.config.models import (
    CameraConfig,
    DetectionConfig,
    DisturbanceConfig,
    GimbalConfig,
    LineMotion,
    SkyLockConfig,
    TargetConfig,
    TargetSetConfig,
    TrackingConfig,
)
from skylock.core.enums import ControlIntentMode, TrackState
from skylock.core.pipeline import TrackingPipeline
from skylock.simulation.source import FixedPointingGimbal, SimulationSource


def test_sim_to_tracker_open_loop() -> None:
    """Moving target inside FOV reaches TRACK in open loop; report state timeline."""
    cam = CameraConfig(
        width=640,
        height=480,
        fov_h_deg=4.0,
        fov_v_deg=3.0,
        fps=30.0,
    )
    # Slow moving target traversing across the sensor center
    target = TargetConfig(
        initial="fixed",
        initial_pos_deg=(0.0, 0.0),
        motion=LineMotion(speed_deg_s=0.2, heading_deg=45.0),
        size_px=10,
        brightness=220.0,
    )
    cfg = SkyLockConfig(
        camera=cam,
        target=TargetSetConfig(count=1, targets=(target,)),
        gimbal=GimbalConfig(initial=(0.0, 0.0)),
        detection=DetectionConfig(),
        tracking=TrackingConfig(confirm_hits=3, confirm_window=5),
        disturbances=DisturbanceConfig(),
    )

    source = SimulationSource(cfg, gimbal=FixedPointingGimbal())
    pipeline = TrackingPipeline(cfg)

    source.open()

    states_visited: list[TrackState] = []
    final_state: TrackState = TrackState.SEARCH

    # Process 60 frames (2 seconds)
    for _ in range(60):
        frame = source.read()
        assert frame is not None

        out = pipeline.process(frame)
        states_visited.append(out.state)
        final_state = out.state

        if out.state == TrackState.TRACK:
            assert out.estimate is not None
            assert out.intent.mode == ControlIntentMode.TRACK
            assert out.intent.image_error_px is not None

    source.close()

    # Timeline of state transitions
    events = pipeline.events
    timeline = [
        f"t={e.timestamp_s:.3f}s: {e.from_state} -> {e.to_state} ({e.reason})"
        for e in events
    ]
    print("\n--- Open-Loop State Timeline ---")
    for entry in timeline:
        print(entry)

    # Verification: Must transition SEARCH -> ACQUIRE -> TRACK
    assert any(
        e.from_state == TrackState.SEARCH and e.to_state == TrackState.ACQUIRE for e in events
    )
    assert any(
        e.from_state == TrackState.ACQUIRE and e.to_state == TrackState.TRACK for e in events
    )
    assert TrackState.TRACK in states_visited
    assert final_state == TrackState.TRACK
