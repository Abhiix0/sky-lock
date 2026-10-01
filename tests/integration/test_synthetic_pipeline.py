"""Integration tests for TrackingPipeline on synthetic frames (no simulator).

Tests complete lifecycle:
appear -> TRACK -> 8 blank frames -> LOST -> reappear near prediction -> TRACK
-> coast timeout -> REACQUIRE -> reappear inside spiral -> TRACK
-> never reappear -> SEARCH.
Verifies pipeline execution with and without pointing telemetry.
"""

from __future__ import annotations

import pytest

from skylock.config.models import CameraConfig, SkyLockConfig, TrackingConfig
from skylock.core.enums import TrackState
from skylock.core.pipeline import TrackingPipeline
from skylock.core.types import PipelineOutput, Pointing
from tests.helpers.synthetic import make_frame


@pytest.mark.parametrize("use_pointing", [True, False])
def test_synthetic_pipeline_lifecycle(use_pointing: bool) -> None:
    cam = CameraConfig(width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0)
    trk = TrackingConfig(
        confirm_hits=3,
        confirm_window=5,
        acquire_timeout_s=1.0,
        lost_after_misses=5,
        coast_max_s=0.25,
        reacquire_timeout_s=0.40,
    )
    cfg = SkyLockConfig(camera=cam, tracking=trk)
    pipeline = TrackingPipeline(cfg)

    pointing = Pointing(pan_deg=15.0, tilt_deg=-5.0) if use_pointing else None
    dt = 0.033
    t = 0.0
    frame_idx = 0

    target_blob = [(320.0, 240.0, 10.0, 220.0)]

    def step_frame(blobs: list[tuple[float, float, float, float]] | None = None) -> PipelineOutput:
        nonlocal frame_idx, t
        f = make_frame(
            size=(480, 640),
            blobs=blobs,
            frame_index=frame_idx,
            timestamp_s=t,
            pointing=pointing,
        )
        return pipeline.process(f)

    # 1. Appear -> TRACK
    # In SEARCH initially
    out = step_frame(target_blob)
    assert out.state == TrackState.ACQUIRE

    # Feed frames until confirmed (confirm_hits = 3)
    for _ in range(2):
        t += dt
        frame_idx += 1
        out = step_frame(target_blob)

    assert out.state == TrackState.TRACK
    assert out.estimate is not None

    # 2. 8 blank frames -> LOST (lost_after_misses = 5)
    for _ in range(8):
        t += dt
        frame_idx += 1
        out = step_frame([])

    assert out.state == TrackState.LOST
    assert out.estimate is not None  # Kalman coasting prediction

    # 3. Reappear near prediction -> TRACK
    t += dt
    frame_idx += 1
    out = step_frame(target_blob)
    assert out.state == TrackState.TRACK

    # 4. Disappear past coast_max_s (0.25s) -> REACQUIRE
    # 5 misses to enter LOST
    for _ in range(5):
        t += dt
        frame_idx += 1
        out = step_frame([])
    assert out.state == TrackState.LOST

    # Coast past 0.25s
    lost_start = pipeline.tracker.state_machine.state_start_time
    while (t - lost_start) <= 0.27:
        t += dt
        frame_idx += 1
        out = step_frame([])
    assert out.state == TrackState.REACQUIRE

    # Reappear inside spiral -> ACQUIRE -> TRACK
    for _ in range(3):
        t += dt
        frame_idx += 1
        out = step_frame(target_blob)

    assert out.state == TrackState.TRACK

    # 5. Never reappear -> SEARCH
    # Misses -> LOST
    for _ in range(5):
        t += dt
        frame_idx += 1
        out = step_frame([])
    assert out.state == TrackState.LOST

    # Coast past 0.25s -> REACQUIRE
    lost_start = pipeline.tracker.state_machine.state_start_time
    while (t - lost_start) <= 0.27:
        t += dt
        frame_idx += 1
        out = step_frame([])
    assert out.state == TrackState.REACQUIRE

    # Blank frames past reacquire_timeout_s (0.40s) -> SEARCH
    reacquire_start = pipeline.tracker.state_machine.state_start_time
    while (t - reacquire_start) <= 0.45:
        t += dt
        frame_idx += 1
        out = step_frame([])

    assert out.state == TrackState.SEARCH
    assert out.estimate is None

    # Verify event history recorded in state machine
    events = pipeline.events
    assert len(events) >= 6
    for ev in events:
        assert ev.t >= 0.0
        assert len(ev.reason) > 0
