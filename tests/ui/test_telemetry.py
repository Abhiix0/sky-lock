"""Unit and snapshot tests for TelemetryPanel and CameraView."""

from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from skylock.core.enums import TrackState
from skylock.ui.panels.telemetry import TelemetryPanel
from skylock.ui.widgets.camera_view import CameraView
from skylock.ui.worker import FrameView

pytestmark = pytest.mark.gui


def _make_dummy_frameview(**kwargs) -> FrameView:
    """Helper to build a FrameView with sensible defaults."""
    default_img = np.zeros((240, 320), dtype=np.uint8)
    defaults = {
        "image": default_img,
        "frame_index": 0,
        "timestamp_s": 0.0,
        "track_state": TrackState.SEARCH,
        "detections": (),
        "estimate": None,
        "gate_px": 20.0,
        "boresight_px": (160.0, 120.0),
        "pointing_pan_deg": 0.0,
        "pointing_tilt_deg": 0.0,
        "ground_truth_px": None,
        "is_simulation": True,
        "fps_pipeline": None,
        "fps_wall": None,
        "latency_ms": None,
        "acquisition_time_s": None,
        "tracking_error_px": None,
        "is_locked": False,
        "control_mode": "AUTO",
        "command_pan_rate": 0.0,
        "command_tilt_rate": 0.0,
        "dropped_ui_frames": 0,
        "n_detections": 0,
        "best_detection_px": None,
        "state_history_tail": (),
        "live": {},
        "total_frames": None,
    }
    defaults.update(kwargs)
    return FrameView(**defaults)


class TestTelemetryPanel:
    """Test TelemetryPanel formatting and None-safe em dash contracts."""

    def test_all_none_renders_em_dash(self, qapp) -> None:
        """When metrics are None, every metric readout label must render as '—', never '0'."""
        panel = TelemetryPanel()
        panel.show()

        fv = _make_dummy_frameview()
        panel.update_telemetry(fv)

        em_dash = "—"
        # Phase 1 compact panel: only the approved essential fields
        assert panel.lbl_best_centroid.text() == em_dash
        assert panel.lbl_est_pos.text() == em_dash
        assert panel.lbl_acq_time.text() == em_dash
        assert panel.lbl_track_err.text() == em_dash
        assert panel.lbl_fps_pipe.text() == em_dash
        assert panel.lbl_last_reacq.text() == em_dash

        panel.close()

    def test_values_formatted_with_decimals(self, qapp) -> None:
        """Verify numeric formatting with specified decimal places."""
        panel = TelemetryPanel()
        panel.show()

        fv = _make_dummy_frameview(
            n_detections=2,
            best_detection_px=(155.34, 118.78),
            estimate=(162.46, 121.89),
            boresight_px=(160.0, 120.0),
            acquisition_time_s=1.23456,
            tracking_error_px=3.456,
            fps_pipeline=59.87,
            fps_wall=29.94,
            latency_ms=16.789,
            live={
                "lock_retention": 0.9456,
                "loss_events": 2,
                "last_reacq_s": 0.450,
                "state_frames": {
                    "SEARCH": 10,
                    "ACQUIRE": 5,
                    "TRACK": 85,
                    "LOST": 2,
                    "REACQUIRE": 3,
                },
            },
        )
        panel.update_telemetry(fv)

        # Phase 1 compact panel: only essential fields
        assert panel.lbl_det_count.text() == "2"
        assert panel.lbl_best_centroid.text() == "(155.3, 118.8)"
        assert panel.lbl_est_pos.text() == "(162.5, 121.9)"
        assert panel.lbl_acq_time.text() == "1.235"
        assert panel.lbl_track_err.text() == "3.46"
        assert panel.lbl_fps_pipe.text() == "59.9"
        assert panel.lbl_last_reacq.text() == "0.450"

        panel.close()

    def test_mp4_frameview_shows_em_dash_for_truth(self, qapp) -> None:
        """MP4 FrameView must show em dash and tooltip for truth-dependent metrics."""
        panel = TelemetryPanel()
        panel.show()

        fv = _make_dummy_frameview(
            is_simulation=False,
            frame_index=15,
            total_frames=100,
            acquisition_time_s=None,
            tracking_error_px=None,
        )
        panel.update_telemetry(fv)

        em_dash = "—"
        assert panel.lbl_acq_time.text() == em_dash
        assert panel.lbl_track_err.text() == em_dash
        assert panel.lbl_acq_time.toolTip() == "needs ground truth"
        assert panel.lbl_track_err.toolTip() == "needs ground truth"

        panel.close()


    def test_telemetry_phase1_essential_fields_only(self, qapp) -> None:
        """Phase 1: TelemetryPanel must have only approved essential fields."""
        panel = TelemetryPanel()
        panel.show()

        # Must exist
        essential = [
            "badge", "lbl_lock",
            "lbl_det_count", "lbl_best_centroid", "lbl_est_pos",
            "lbl_pan", "lbl_tilt",
            "lbl_acq_time", "lbl_track_err", "lbl_last_reacq", "lbl_fps_pipe",
        ]
        for attr in essential:
            assert hasattr(panel, attr), f"Essential field {attr!r} missing from TelemetryPanel"

        # Must NOT exist (removed in Phase 1)
        removed = [
            "lbl_fps_wall", "lbl_latency", "lbl_cmd_rate",
            "lbl_lock_retention", "lbl_loss_events", "lbl_state_times",
            "lbl_est_offset", "lbl_progress", "lbl_source",
        ]
        for attr in removed:
            assert not hasattr(panel, attr), (
                f"Removed field {attr!r} must not exist on TelemetryPanel (Phase 1)"
            )

        panel.close()


class TestCameraViewSnapshot:
    """Test CameraView grab() paintEvent safety under diverse geometries and states."""

    @pytest.mark.parametrize(
        "img_shape",
        [(240, 320), (480, 640)],
        ids=["320x240", "640x480"],
    )
    def test_paint_event_no_estimate(self, qapp, img_shape: tuple[int, int]) -> None:
        cam = CameraView()
        cam.resize(400, 300)
        cam.show()

        img = np.zeros(img_shape, dtype=np.uint8)
        fv = _make_dummy_frameview(image=img, estimate=None)
        cam.update_frame(fv)

        pixmap = cam.grab()
        assert not pixmap.isNull()
        cam.close()

    def test_paint_event_with_estimate_and_predictions(self, qapp) -> None:
        cam = CameraView()
        cam.resize(640, 480)
        cam.show()

        # State TRACK
        fv_track = _make_dummy_frameview(
            estimate=(160.0, 120.0),
            track_state=TrackState.TRACK,
            detections=((160.0, 120.0, 10.0, 10.0),),
        )
        cam.update_frame(fv_track)
        pix1 = cam.grab()
        assert not pix1.isNull()

        # State LOST (triggers dashed crosshair branch)
        fv_lost = _make_dummy_frameview(
            estimate=(170.0, 130.0),
            track_state=TrackState.LOST,
        )
        cam.update_frame(fv_lost)
        pix2 = cam.grab()
        assert not pix2.isNull()

        cam.close()

    def test_paint_event_gt_on_off_and_legend(self, qapp) -> None:
        cam = CameraView()
        cam.resize(500, 400)
        cam.show()

        fv = _make_dummy_frameview(
            is_simulation=True,
            ground_truth_px=(165.0, 125.0),
            estimate=(160.0, 120.0),
        )
        cam.update_frame(fv)

        # GT off, legend off
        cam.show_ground_truth = False
        cam.show_legend = False
        assert not cam.grab().isNull()

        # GT on, legend on
        cam.show_ground_truth = True
        cam.show_legend = True
        assert not cam.grab().isNull()

        cam.close()

    def test_paint_event_tiny_widget(self, qapp) -> None:
        """Tiny 1x1 widget must not crash due to zero-division or out of bounds."""
        cam = CameraView()
        cam.resize(1, 1)
        cam.show()

        fv = _make_dummy_frameview(estimate=(160.0, 120.0))
        cam.update_frame(fv)

        pix = cam.grab()
        assert not pix.isNull()
        cam.close()
