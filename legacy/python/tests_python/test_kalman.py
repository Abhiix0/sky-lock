"""Tests for skylock.kalman — constant-velocity Kalman filter."""

import math

import pytest

from skylock.kalman import KalmanFilter


class TestKalmanInit:
    """Initialization and reset."""

    def test_not_initialized_by_default(self):
        kf = KalmanFilter()
        assert kf.is_initialized is False

    def test_init_sets_state(self):
        kf = KalmanFilter()
        kf.init(45.0, 10.0, 1.0)
        assert kf.is_initialized is True
        state = kf.get_state()
        assert state["pan_deg"] == pytest.approx(45.0)
        assert state["tilt_deg"] == pytest.approx(10.0)
        assert state["pan_rate_deg_s"] == pytest.approx(0.0)
        assert state["tilt_rate_deg_s"] == pytest.approx(0.0)

    def test_reset_clears_state(self):
        kf = KalmanFilter()
        kf.init(45.0, 10.0, 1.0)
        kf.reset()
        assert kf.is_initialized is False


class TestKalmanPredict:
    """Prediction step."""

    def test_constant_velocity_prediction(self):
        """Prediction should propagate position using velocity."""
        kf = KalmanFilter()
        kf.init(0.0, 0.0, 0.0)
        # Inject velocity through update sequence
        kf.update(1.0, 0.5, 0.1)  # ~10 deg/s pan, ~5 deg/s tilt
        kf.update(2.0, 1.0, 0.2)

        state_before = kf.get_state()
        kf.predict(0.3)
        state_after = kf.get_state()

        # Position should have advanced by velocity * dt
        assert state_after["unwrapped_pan_deg"] > state_before["unwrapped_pan_deg"]

    def test_predict_with_zero_dt_is_noop(self):
        kf = KalmanFilter()
        kf.init(10.0, 20.0, 1.0)
        state1 = kf.get_state()
        kf.predict(1.0)  # same time
        state2 = kf.get_state()
        assert state2["pan_deg"] == pytest.approx(state1["pan_deg"])

    def test_predict_before_init_is_noop(self):
        kf = KalmanFilter()
        kf.predict(1.0)  # should not crash
        assert kf.is_initialized is False


class TestKalmanUpdate:
    """Measurement update step."""

    def test_update_before_init_initializes(self):
        kf = KalmanFilter()
        kf.update(30.0, 15.0, 0.5)
        assert kf.is_initialized is True
        assert kf.get_state()["pan_deg"] == pytest.approx(30.0)

    def test_repeated_updates_converge(self):
        """Updates at the same position should converge and reduce uncertainty."""
        kf = KalmanFilter()
        for i in range(20):
            kf.update(50.0, 25.0, i * 0.1)

        state = kf.get_state()
        assert state["pan_deg"] == pytest.approx(50.0, abs=0.5)
        assert state["tilt_deg"] == pytest.approx(25.0, abs=0.5)
        # Velocity should approach zero
        assert abs(state["pan_rate_deg_s"]) < 1.0
        assert abs(state["tilt_rate_deg_s"]) < 1.0

    def test_position_sigma_decreases_with_updates(self):
        """Uncertainty should decrease with repeated measurements."""
        kf = KalmanFilter()
        kf.init(0.0, 0.0, 0.0)
        sigma_before = kf.get_position_sigma_deg()

        for i in range(1, 11):
            kf.update(0.0, 0.0, i * 0.1)

        sigma_after = kf.get_position_sigma_deg()
        assert sigma_after < sigma_before


class TestKalmanInnovationGate:
    """Mahalanobis innovation gating."""

    def test_close_measurement_has_small_gate(self):
        kf = KalmanFilter()
        kf.init(10.0, 5.0, 0.0)
        gate = kf.get_innovation_gate(10.01, 5.01)
        assert gate < 1.0

    def test_far_measurement_has_large_gate(self):
        kf = KalmanFilter()
        kf.init(10.0, 5.0, 0.0)
        gate = kf.get_innovation_gate(100.0, 80.0)
        assert gate > 10.0

    def test_uninitialized_returns_infinity(self):
        kf = KalmanFilter()
        gate = kf.get_innovation_gate(10.0, 5.0)
        assert gate == math.inf
