"""Unit tests for Tracker orchestrator (measurement selection, ROI calculation, ControlIntent)."""

from __future__ import annotations

import numpy as np
import pytest

from skylock.config.models import CameraConfig, DetectionConfig, GimbalConfig, SkyLockConfig, TrackingConfig
from skylock.core.enums import ControlIntentMode, TrackState
from skylock.core.types import Detection, Frame, Pointing
from skylock.tracking.tracker import Tracker


def _make_frame(
    index: int = 0,
    timestamp_s: float = 0.0,
    pointing: Pointing | None = None,
    width: int = 640,
    height: int = 512,
) -> Frame:
    img = np.zeros((height, width), dtype=np.uint8)
    return Frame(
        image=img,
        index=index,
        timestamp_s=timestamp_s,
        source_id="unit_test",
        pointing=pointing,
    )


def test_tracker_roi_behavior() -> None:
    cam = CameraConfig(width=640, height=512, fov_h_deg=4.0, fov_v_deg=3.2)
    det_cfg = DetectionConfig(roi_margin_px=48)
    trk_cfg = TrackingConfig()
    cfg = SkyLockConfig(camera=cam, detection=det_cfg, tracking=trk_cfg)

    tracker = Tracker(cfg)

    # In SEARCH, ROI is None (full frame)
    assert tracker.state == TrackState.SEARCH
    assert tracker.get_roi() is None

    # Step to ACQUIRE and then TRACK
    det = Detection(
        cx=320.0, cy=256.0, area_px=20.0, peak=200.0, snr=10.0, bbox=(310, 246, 20, 20)
    )

    # Confirm candidate over required hits (3 hits)
    for i in range(3):
        tracker.step(_make_frame(i, i * 0.033), [det])

    assert tracker.state == TrackState.TRACK
    roi = tracker.get_roi()
    assert roi is not None
    x, y, w, h = roi
    # Centered around (320, 256) with margin 48 -> width and height should be ~96
    assert abs((x + w / 2.0) - 320.0) < 5.0
    assert abs((y + h / 2.0) - 256.0) < 5.0
    assert w <= 2 * det_cfg.roi_margin_px + 2
    assert h <= 2 * det_cfg.roi_margin_px + 2


def test_tracker_measurement_selection_in_track() -> None:
    cam = CameraConfig(width=640, height=512, fov_h_deg=3.0, fov_v_deg=2.4)
    gimbal = GimbalConfig(pan_limit_deg=(-4.0, 4.0), tilt_limit_deg=(-4.0, 4.0))
    cfg = SkyLockConfig(camera=cam, gimbal=gimbal)
    tracker = Tracker(cfg)

    # Move to TRACK with target at center
    det_true = Detection(
        cx=320.0, cy=256.0, area_px=20.0, peak=200.0, snr=10.0, bbox=(310, 246, 20, 20)
    )
    for i in range(3):
        tracker.step(_make_frame(i, i * 0.033), [det_true])
    assert tracker.state == TrackState.TRACK

    # In TRACK, present two detections: one close to Kalman prediction, one far (clutter)
    det_near = Detection(
        cx=321.0, cy=256.0, area_px=20.0, peak=150.0, snr=8.0, bbox=(311, 246, 20, 20)
    )
    det_clutter = Detection(
        cx=450.0, cy=400.0, area_px=30.0, peak=250.0, snr=15.0, bbox=(440, 390, 20, 20)
    )

    _state, estimate, selected, _intent = tracker.step(
        _make_frame(3, 0.1), [det_clutter, det_near]
    )

    assert estimate is not None
    assert selected is not None
    # Nearest detection (det_near) should be selected despite clutter having higher peak/snr
    assert abs(selected.cx - 321.0) < 1.0


def test_tracker_control_intent_modes() -> None:
    cam = CameraConfig(width=640, height=512, fov_h_deg=4.0, fov_v_deg=3.2)
    cfg = SkyLockConfig(camera=cam)
    tracker = Tracker(cfg)

    boresight_x = (cam.width - 1.0) / 2.0
    boresight_y = (cam.height - 1.0) / 2.0

    # 1. SEARCH -> GOTO raster
    frame0 = _make_frame(0, 0.0)
    state, est, _cand, intent = tracker.step(frame0, [])
    assert state == TrackState.SEARCH
    assert intent.mode == ControlIntentMode.GOTO
    assert intent.image_error_px is None

    # 2. ACQUIRE / TRACK -> TRACK with image_error_px
    det = Detection(
        cx=340.0, cy=270.0, area_px=20.0, peak=200.0, snr=10.0, bbox=(330, 260, 20, 20)
    )
    for i in range(1, 4):
        state, est, _cand, intent = tracker.step(_make_frame(i, i * 0.033), [det])

    assert state == TrackState.TRACK
    assert intent.mode == ControlIntentMode.TRACK
    assert intent.image_error_px is not None
    err_x, err_y = intent.image_error_px
    assert err_x == pytest.approx(340.0 - boresight_x, abs=2.0)
    assert err_y == pytest.approx(270.0 - boresight_y, abs=2.0)


def test_tracker_pointing_telemetry_none() -> None:
    """Tracker works seamlessly when frame.pointing is None."""
    tracker = Tracker()
    frame = _make_frame(0, 0.0, pointing=None)
    state, est, cand, intent = tracker.step(frame, [])
    assert state == TrackState.SEARCH
    assert intent.mode == ControlIntentMode.GOTO
