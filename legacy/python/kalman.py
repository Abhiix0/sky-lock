"""
Constant-velocity Kalman Filter for 2D body-frame Line-of-Sight tracking.

State vector: [pan, tilt, panRate, tiltRate]^T (degrees and deg/s).
Pan angle state is kept continuous (unwrapped) to prevent covariance
divergence across the ±180° seam.

JS reference: src/tracking/kalman.js
"""

from __future__ import annotations

import math

import numpy as np

from skylock.config import KALMAN, KalmanConfig
from skylock.geometry import angular_diff_deg, wrap_deg


class KalmanFilter:
    """Constant-velocity Kalman filter for 2-axis angular tracking.

    The filter maintains a 4-element state vector and 4×4 covariance matrix.
    Pan and tilt axes are treated as decoupled for computational efficiency.

    Args:
        config: Kalman filter tuning parameters.
    """

    def __init__(self, config: KalmanConfig = KALMAN) -> None:
        self._cfg = config

        # State: [pan, tilt, panRate, tiltRate]
        self._x = np.zeros(4, dtype=np.float64)

        # Covariance matrix 4×4
        self._P = np.zeros((4, 4), dtype=np.float64)

        self._last_time: float = 0.0
        self._initialized: bool = False

    @property
    def is_initialized(self) -> bool:
        """Whether the filter has been initialized with a first measurement."""
        return self._initialized

    def _reset_covariance(self) -> None:
        """Reset covariance matrix with initial uncertainty."""
        self._P.fill(0.0)
        r_meas = self._cfg.r_meas_deg
        self._P[0, 0] = r_meas * r_meas  # var(pan)
        self._P[1, 1] = r_meas * r_meas  # var(tilt)
        self._P[2, 2] = 400.0  # var(panRate) ~ 20 deg/s sigma
        self._P[3, 3] = 400.0  # var(tiltRate) ~ 20 deg/s sigma

    def init(self, meas_pan: float, meas_tilt: float, t: float) -> None:
        """Initialize filter state with first measurement.

        Args:
            meas_pan: Measured pan in degrees.
            meas_tilt: Measured tilt in degrees.
            t: Simulation time in seconds.
        """
        self._x[0] = meas_pan
        self._x[1] = meas_tilt
        self._x[2] = 0.0
        self._x[3] = 0.0
        self._reset_covariance()
        self._last_time = t
        self._initialized = True

    def predict(self, t: float) -> None:
        """Predict state and propagate covariance forward to time t.

        Args:
            t: Target simulation time in seconds.
        """
        if not self._initialized:
            return
        dt = t - self._last_time
        if dt <= 0.0:
            return

        # State transition: x_new = x + dt * v
        self._x[0] += dt * self._x[2]
        self._x[1] += dt * self._x[3]

        # Discrete white-noise acceleration model
        q = self._cfg.q_accel_deg_s2
        dt2 = dt * dt
        dt3 = dt2 * dt
        q00 = q * (dt3 / 3.0)
        q01 = q * (dt2 / 2.0)
        q11 = q * dt

        P = self._P

        # Pan axis propagation (indices 0, 2)
        p00, p02, p20, p22 = P[0, 0], P[0, 2], P[2, 0], P[2, 2]
        P[0, 0] = p00 + dt * (p20 + p02) + dt2 * p22 + q00
        P[0, 2] = p02 + dt * p22 + q01
        P[2, 0] = p20 + dt * p22 + q01
        P[2, 2] = p22 + q11

        # Tilt axis propagation (indices 1, 3)
        p11, p13, p31, p33 = P[1, 1], P[1, 3], P[3, 1], P[3, 3]
        P[1, 1] = p11 + dt * (p31 + p13) + dt2 * p33 + q00
        P[1, 3] = p13 + dt * p33 + q01
        P[3, 1] = p31 + dt * p33 + q01
        P[3, 3] = p33 + q11

        self._last_time = t

    def get_innovation_gate(self, meas_pan: float, meas_tilt: float) -> float:
        """Calculate Mahalanobis distance of a candidate measurement.

        Args:
            meas_pan: Candidate pan in degrees.
            meas_tilt: Candidate tilt in degrees.

        Returns:
            Normalized Mahalanobis distance in standard deviations (sigmas).
        """
        if not self._initialized:
            return math.inf

        # Unwrap measurement relative to unwrapped predicted pan
        y_pan = angular_diff_deg(meas_pan, self._x[0])
        y_tilt = meas_tilt - self._x[1]

        r2 = self._cfg.r_meas_deg**2
        s00 = self._P[0, 0] + r2
        s11 = self._P[1, 1] + r2

        d2 = (y_pan * y_pan) / s00 + (y_tilt * y_tilt) / s11
        return math.sqrt(max(0.0, d2))

    def update(self, meas_pan: float, meas_tilt: float, t: float) -> None:
        """Update filter state with observation at time t.

        Args:
            meas_pan: Measured pan in degrees.
            meas_tilt: Measured tilt in degrees.
            t: Simulation time in seconds.
        """
        if not self._initialized:
            self.init(meas_pan, meas_tilt, t)
            return

        self.predict(t)

        # Innovation y = z - Hx (unwrapped pan error)
        y_pan = angular_diff_deg(meas_pan, self._x[0])
        y_tilt = meas_tilt - self._x[1]

        r2 = self._cfg.r_meas_deg**2
        P = self._P

        # Innovation covariance S = H P H^T + R
        s00 = P[0, 0] + r2
        s11 = P[1, 1] + r2

        # Kalman gain K = P H^T S^-1
        k00 = P[0, 0] / s00
        k20 = P[2, 0] / s00
        k11 = P[1, 1] / s11
        k31 = P[3, 1] / s11

        # State update x = x + K y
        self._x[0] += k00 * y_pan
        self._x[2] += k20 * y_pan
        self._x[1] += k11 * y_tilt
        self._x[3] += k31 * y_tilt

        # Covariance update P = (I - K H) P
        # Pan block
        p00, p02 = P[0, 0], P[0, 2]
        p20, p22 = P[2, 0], P[2, 2]
        P[0, 0] = (1.0 - k00) * p00
        P[0, 2] = (1.0 - k00) * p02
        P[2, 0] = p20 - k20 * p00
        P[2, 2] = p22 - k20 * p02

        # Tilt block
        p11, p13 = P[1, 1], P[1, 3]
        p31, p33 = P[3, 1], P[3, 3]
        P[1, 1] = (1.0 - k11) * p11
        P[1, 3] = (1.0 - k11) * p13
        P[3, 1] = p31 - k31 * p11
        P[3, 3] = p33 - k31 * p13

    def get_state(self) -> dict[str, float]:
        """Return current estimated line-of-sight state.

        Returns:
            Dict with pan_deg, tilt_deg, pan_rate_deg_s, tilt_rate_deg_s,
            unwrapped_pan_deg.
        """
        return {
            "pan_deg": wrap_deg(self._x[0]),
            "tilt_deg": self._x[1],
            "pan_rate_deg_s": self._x[2],
            "tilt_rate_deg_s": self._x[3],
            "unwrapped_pan_deg": self._x[0],
        }

    def get_predicted(self, t: float) -> dict[str, float]:
        """Get predicted state at future time t without advancing filter.

        Args:
            t: Simulation time in seconds.

        Returns:
            Dict with pan_deg, tilt_deg, pan_rate_deg_s, tilt_rate_deg_s.
        """
        if not self._initialized:
            return self.get_state()
        dt = t - self._last_time
        pred_pan = self._x[0] + dt * self._x[2]
        pred_tilt = self._x[1] + dt * self._x[3]
        return {
            "pan_deg": wrap_deg(pred_pan),
            "tilt_deg": pred_tilt,
            "pan_rate_deg_s": self._x[2],
            "tilt_rate_deg_s": self._x[3],
        }

    def get_position_sigma_deg(self) -> float:
        """Get position uncertainty standard deviation in degrees."""
        r_meas = self._cfg.r_meas_deg
        return math.sqrt(max(self._P[0, 0], self._P[1, 1]) + r_meas * r_meas)

    def reset(self) -> None:
        """Reset filter to uninitialized state."""
        self._x.fill(0.0)
        self._P.fill(0.0)
        self._last_time = 0.0
        self._initialized = False
