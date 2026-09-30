"""Unit tests for the 4-state constant-velocity Kalman filter."""

from __future__ import annotations

import math

import numpy as np
import pytest

from skylock.config.models import CameraConfig, KalmanConfig
from skylock.core.geometry import wrap_deg
from skylock.tracking.kalman import KalmanFilter


def test_kalman_initialization_and_reset() -> None:
    kf = KalmanFilter()
    assert not kf.is_initialized

    kf.init(np.array([45.0, -10.0]), t=1.0)
    assert kf.is_initialized
    assert kf.state[0] == pytest.approx(45.0)
    assert kf.state[1] == pytest.approx(-10.0)
    assert kf.state[2] == pytest.approx(0.0)
    assert kf.state[3] == pytest.approx(0.0)
    assert kf.timestamp_s == pytest.approx(1.0)

    kf.reset()
    assert not kf.is_initialized
    assert math.isinf(kf.mahalanobis(np.array([0.0, 0.0])))


def test_kalman_irregular_dt_and_dt_guard() -> None:
    kf = KalmanFilter()
    kf.init(np.array([0.0, 0.0]), t=1.0)

    # dt <= 0 should be guarded / no-op
    kf.predict(t=0.5)
    assert kf.timestamp_s == pytest.approx(1.0)
    assert kf.state[0] == pytest.approx(0.0)

    # Irregular dt increments
    dts = [0.033, 0.016, 0.050, 0.022]
    current_t = 1.0
    for dt in dts:
        current_t += dt
        kf.predict(t=current_t)
        assert kf.timestamp_s == pytest.approx(current_t)


def test_kalman_cv_track_convergence() -> None:
    """Kalman convergence on constant-velocity track (RMS < 0.3 px after 1 s)."""
    cam = CameraConfig(width=640, height=512, fov_h_deg=3.0, fov_v_deg=2.4)
    deg_per_px = cam.fov_h_deg / cam.width
    px_noise_std = 0.2
    r_deg = px_noise_std * deg_per_px
    R = np.diag([r_deg**2, r_deg**2])

    cfg = KalmanConfig(q_accel_deg_s2=25.0, r_meas_px=1.0, gate_sigma=4.0)
    kf = KalmanFilter(cfg, ifov_deg=deg_per_px)

    v_pan = 0.5
    v_tilt = 0.2
    dt = 1.0 / 30.0  # 30 Hz

    rng = np.random.default_rng(42)

    t = 0.0
    true_pan = 2.0
    true_tilt = 1.0

    kf.init(np.array([true_pan, true_tilt]), t=t)

    errors_after_1s: list[float] = []

    for i in range(1, 90):
        t = i * dt
        true_pan += v_pan * dt
        true_tilt += v_tilt * dt

        kf.predict(t=t)

        meas_noise = rng.normal(0.0, r_deg, size=2)
        meas = np.array([true_pan + meas_noise[0], true_tilt + meas_noise[1]])

        kf.update(meas, t=t, R=R)

        if t >= 1.0:
            err_pan = kf.state[0] - true_pan
            err_tilt = kf.state[1] - true_tilt
            err_deg = math.hypot(err_pan, err_tilt)
            err_px = err_deg / deg_per_px
            errors_after_1s.append(err_px)

    rms_px = math.sqrt(float(np.mean(np.square(errors_after_1s))))
    assert rms_px < 0.3, f"RMS position error {rms_px:.4f} px exceeds 0.3 px threshold"


def test_kalman_nis_consistency() -> None:
    """NIS mean should be in [0.5, 2.0]*dof over 500 steps (dof=2)."""
    cfg = KalmanConfig(q_accel_deg_s2=4.0, r_meas_px=1.0, gate_sigma=4.0)
    deg_per_px = 3.0 / 640.0
    kf = KalmanFilter(cfg, ifov_deg=deg_per_px)

    dt = 1.0 / 30.0
    dof = 2
    steps = 500

    q = cfg.q_accel_deg_s2
    Q_block = np.array([[q * dt**3 / 3.0, q * dt**2 / 2.0], [q * dt**2 / 2.0, q * dt]])
    r_deg2 = (cfg.r_meas_px * deg_per_px) ** 2
    R = np.diag([r_deg2, r_deg2])

    rng = np.random.default_rng(12345)
    x_true = np.zeros(4, dtype=np.float64)
    kf.init((0.0, 0.0), 0.0)

    nis_values: list[float] = []

    for i in range(1, steps + 1):
        t = i * dt
        w_pan = rng.multivariate_normal([0.0, 0.0], Q_block)
        w_tilt = rng.multivariate_normal([0.0, 0.0], Q_block)
        x_true[0] = wrap_deg(x_true[0] + x_true[2] * dt + w_pan[0])
        x_true[2] += w_pan[1]
        x_true[1] += x_true[3] * dt + w_tilt[0]
        x_true[3] += w_tilt[1]

        kf.predict(t=t)

        meas = np.array([x_true[0], x_true[1]]) + rng.normal(0.0, math.sqrt(r_deg2), size=2)

        dm = kf.mahalanobis((meas[0], meas[1]), R=R)
        nis_values.append(dm**2)

        kf.update((meas[0], meas[1]), t=t, R=R)

    mean_nis = float(np.mean(nis_values))
    expected_min = 0.5 * dof
    expected_max = 2.0 * dof
    assert expected_min <= mean_nis <= expected_max, (
        f"Mean NIS {mean_nis:.3f} outside [{expected_min}, {expected_max}]"
    )
