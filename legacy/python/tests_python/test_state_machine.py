"""Tests for skylock.state_machine — FSOC acquisition logic."""

from skylock.config import TrackingConfig
from skylock.kalman import KalmanFilter
from skylock.state_machine import StateMachine


class TestStateMachine:
    def test_initial_state_is_search(self):
        sm = StateMachine()
        assert sm.state == "SEARCH"

    def test_search_to_acquire_transition(self):
        sm = StateMachine()
        detections = [{"cx": 320.0, "cy": 240.0, "snr": 10.0}]
        gimbal_state = {"pan_deg": 0.0, "tilt_deg": 0.0}

        result = sm.update(1.0, detections, gimbal_state)

        assert result["state"] == "ACQUIRE"
        assert sm.state == "ACQUIRE"
        assert result["selected_detection"] == detections[0]

    def test_acquire_to_track_transition(self):
        config = TrackingConfig(acquire_confirm_frames=3)
        sm = StateMachine(config)
        kalman = KalmanFilter()
        detections = [{"cx": 320.0, "cy": 240.0, "snr": 10.0}]
        gimbal_state = {"pan_deg": 0.0, "tilt_deg": 0.0}

        # Frame 1: SEARCH -> ACQUIRE
        sm.update(1.0, detections, gimbal_state)
        assert sm.state == "ACQUIRE"

        # Frame 2: ACQUIRE (confirm 2)
        sm.update(1.1, detections, gimbal_state)
        assert sm.state == "ACQUIRE"

        # Frame 3: ACQUIRE -> TRACK (confirm 3)
        result = sm.update(1.2, detections, gimbal_state, kalman=kalman)
        assert result["state"] == "TRACK"
        assert sm.state == "TRACK"
        assert kalman.is_initialized

    def test_acquire_timeout_returns_to_search(self):
        config = TrackingConfig(acquire_timeout_sec=1.0)
        sm = StateMachine(config)
        detections = [{"cx": 320.0, "cy": 240.0, "snr": 10.0}]
        gimbal_state = {"pan_deg": 0.0, "tilt_deg": 0.0}

        # Frame 1: SEARCH -> ACQUIRE
        sm.update(1.0, detections, gimbal_state)
        assert sm.state == "ACQUIRE"

        # Frame 2: No detections, after timeout
        empty_detections = []
        result = sm.update(2.5, empty_detections, gimbal_state)
        assert result["state"] == "SEARCH"
        assert sm.state == "SEARCH"

    def test_track_to_lost_transition(self):
        config = TrackingConfig(acquire_confirm_frames=1, lost_miss_frames=2)
        sm = StateMachine(config)
        kalman = KalmanFilter()
        detections = [{"cx": 320.0, "cy": 240.0, "snr": 10.0}]
        gimbal_state = {"pan_deg": 0.0, "tilt_deg": 0.0}

        # SEARCH -> ACQUIRE
        sm.update(1.0, detections, gimbal_state, kalman=kalman)
        # ACQUIRE -> TRACK
        sm.update(1.1, detections, gimbal_state, kalman=kalman)
        assert sm.state == "TRACK"

        # Miss 1
        empty_detections = []
        sm.update(1.2, empty_detections, gimbal_state, kalman=kalman)
        assert sm.state == "TRACK"

        # Miss 2
        sm.update(1.3, empty_detections, gimbal_state, kalman=kalman)
        assert sm.state == "TRACK"

        # Miss 3 (exceeds lost_miss_frames=2)
        result = sm.update(1.4, empty_detections, gimbal_state, kalman=kalman)
        assert result["state"] == "LOST"
        assert sm.state == "LOST"

    def test_lost_to_reacquire_transition(self):
        config = TrackingConfig(acquire_confirm_frames=1, lost_miss_frames=1, coast_max_sec=2.0)
        sm = StateMachine(config)
        kalman = KalmanFilter()
        detections = [{"cx": 320.0, "cy": 240.0, "snr": 10.0}]
        gimbal_state = {"pan_deg": 0.0, "tilt_deg": 0.0}

        sm.update(1.0, detections, gimbal_state, kalman=kalman)  # SEARCH -> ACQUIRE
        sm.update(1.1, detections, gimbal_state, kalman=kalman)  # ACQUIRE -> TRACK
        sm.update(1.2, [], gimbal_state, kalman=kalman)  # TRACK (miss 1)
        sm.update(1.3, [], gimbal_state, kalman=kalman)  # TRACK -> LOST (miss 2)
        assert sm.state == "LOST"

        # Still in LOST before coast max
        sm.update(2.0, [], gimbal_state, kalman=kalman)
        assert sm.state == "LOST"

        # Exceed coast max
        result = sm.update(4.0, [], gimbal_state, kalman=kalman)
        assert result["state"] == "REACQUIRE"
        assert sm.state == "REACQUIRE"

    def test_reset(self):
        sm = StateMachine()
        sm.state = "TRACK"
        sm.reset()
        assert sm.state == "SEARCH"
        assert len(sm.get_events()) == 0
