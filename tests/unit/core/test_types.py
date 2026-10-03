"""Unit tests for core data models, types, and Frame immutability."""

import numpy as np
import pytest

from skylock.core.enums import ControlIntentMode, TrackState
from skylock.core.errors import FrameError
from skylock.core.types import (
    Candidate,
    ControlCommand,
    ControlIntent,
    Detection,
    Frame,
    GroundTruthSample,
    PipelineOutput,
    Pointing,
    TargetEstimate,
    TargetTruth,
)


def test_frame_valid() -> None:
    img = np.zeros((480, 640), dtype=np.uint8)
    pointing = Pointing(pan_deg=10.0, tilt_deg=-5.0)
    frame = Frame(image=img, index=0, timestamp_s=0.0, source_id="sim", pointing=pointing)
    assert frame.image.shape == (480, 640)
    assert frame.index == 0
    assert frame.pointing == pointing


def test_frame_immutability() -> None:
    img = np.zeros((100, 100), dtype=np.uint8)
    frame = Frame(image=img, index=1, timestamp_s=0.033, source_id="sim")
    with pytest.raises(ValueError, match="read-only"):
        frame.image[0, 0] = 255


def test_frame_rejects_non_uint8() -> None:
    img = np.zeros((100, 100), dtype=np.float32)
    with pytest.raises(FrameError, match="uint8"):
        Frame(image=img, index=0, timestamp_s=0.0, source_id="test")


def test_frame_rejects_3_channels() -> None:
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    with pytest.raises(FrameError, match="2-D monochrome"):
        Frame(image=img, index=0, timestamp_s=0.0, source_id="test")


def test_pipeline_types() -> None:
    det = Detection(cx=320.0, cy=240.0, area_px=10.0, peak=250.0, snr=15.0, bbox=(315, 235, 10, 10))
    cand = Candidate(id=1, cx=320.0, cy=240.0, age=3, hits=3, misses=0, confirmed=True, score=1.0)
    est = TargetEstimate(
        pan_deg=0.0,
        tilt_deg=0.0,
        pan_rate=0.0,
        tilt_rate=0.0,
        px=320.0,
        py=240.0,
        sigma_deg=0.01,
        from_measurement=True,
    )
    intent = ControlIntent(
        mode=ControlIntentMode.TRACK,
        setpoint_pan_deg=0.0,
        setpoint_tilt_deg=0.0,
        image_error_px=(0.0, 0.0),
    )
    cmd = ControlCommand(pan_rate_deg_s=1.5, tilt_rate_deg_s=-0.5)
    assert cmd.pan_rate_deg_s == 1.5

    out = PipelineOutput(
        frame_index=0,
        timestamp_s=0.0,
        state=TrackState.TRACK,
        estimate=est,
        detections=(det,),
        selected=cand,
        intent=intent,
        latency_ms=1.2,
    )
    assert out.state == TrackState.TRACK
    assert len(out.detections) == 1


def test_ground_truth_sample() -> None:
    target_truth = TargetTruth(
        id="t0", az_deg=0.5, el_deg=-0.2, px=330.0, py=230.0, visible=True, in_fov=True
    )
    gt = GroundTruthSample(
        frame_index=5,
        timestamp_s=0.166,
        targets=(target_truth,),
        primary_px=(330.0, 230.0),
        primary_visible=True,
        boresight_error_px=14.14,
        pointing=Pointing(0.0, 0.0),
    )
    assert gt.primary_visible is True
    assert len(gt.targets) == 1
