"""Constant-velocity Kalman filter for 2-axis optical line-of-sight angular tracking."""

from __future__ import annotations

import math

import numpy as np

from skylock.config.models import KalmanConfig
from skylock.core.geometry import angular_diff_deg, wrap_deg


class KalmanFilter:
    """Discrete-time constant-velocity Kalman filter with discrete white-noise acceleration.

    State vector: [pan_deg, tilt_deg, vpan_deg_s, vtilt_deg_s]^T
    Covariance update: Joseph-form formulation for guaranteed numerical positive semi-definiteness.
    """

    def __init__(
        self,
        config: KalmanConfig | None = None,
        ifov_deg: float = 4.0 / 640.0,
    ) -> None:
        self.config = config if config is not None else KalmanConfig()
        self.ifov_deg = float(ifov_deg)

        # State vector [pan, tilt, vpan, vtilt]
        self._x = np.zeros(4, dtype=np.float64)

        # Covariance matrix 4x4
        self._P = np.zeros((4, 4), dtype=np.float64)

        # Default measurement covariance in degrees^2
        r_deg = float(self.config.r_meas_px) * self.ifov_deg
        self._default_R = np.diag([r_deg**2, r_deg**2]).astype(np.float64)

        self._last_time: float = 0.0
        self._initialized: bool = False

    @property
    def is_initialized(self) -> bool:
        """Whether the filter has been initialized with a first observation."""
        return self._initialized

    @property
    def state(self) -> tuple[float, float, float, float]:
        """Current estimated state (pan_deg, tilt_deg, vpan_deg_s, vtilt_deg_s)."""
        return (
            wrap_deg(float(self._x[0])),
            float(self._x[1]),
            float(self._x[2]),
            float(self._x[3]),
        )

    @property
    def position_sigma_deg(self) -> float:
        """Position uncertainty 1-sigma in degrees."""
        var_pos = max(float(self._P[0, 0]), float(self._P[1, 1]))
        r_var = float(self._default_R[0, 0])
        return math.sqrt(max(0.0, var_pos + r_var))

    @property
    def timestamp_s(self) -> float:
        """Most recent state update or prediction timestamp in seconds."""
        return self._last_time

    def init(self, z: tuple[float, float] | np.ndarray, t: float) -> None:
        """Initialize filter state and covariance at observation time t.

        Args:
            z: (pan_deg, tilt_deg) measurement in degrees.
            t: Measurement timestamp in seconds.
        """
        self._x[0] = wrap_deg(float(z[0]))
        self._x[1] = float(z[1])
        self._x[2] = 0.0
        self._x[3] = 0.0

        self._P.fill(0.0)
        r_var = float(self._default_R[0, 0])
        self._P[0, 0] = r_var
        self._P[1, 1] = r_var
        # Initial velocity variance: (20.0 deg/s)^2 = 400.0
        self._P[2, 2] = 400.0
        self._P[3, 3] = 400.0

        self._last_time = float(t)
        self._initialized = True

    def predict(self, t: float) -> tuple[float, float, float, float]:
        """Propagate state and covariance forward to time t.

        Args:
            t: Target timestamp in seconds.

        Returns:
            Predicted state tuple (pan, tilt, vpan, vtilt).
        """
        if not self._initialized:
            return self.state

        dt = float(t) - self._last_time
        if dt <= 0.0:
            return self.state

        # State transition matrix F
        F = np.array(
            [
                [1.0, 0.0, dt, 0.0],
                [0.0, 1.0, 0.0, dt],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

        self._x = F @ self._x

        # Discrete white-noise acceleration process noise Q
        q = float(self.config.q_accel_deg_s2)
        dt2 = dt * dt
        dt3 = dt2 * dt
        q00 = q * (dt3 / 3.0)
        q01 = q * (dt2 / 2.0)
        q11 = q * dt

        Q = np.zeros((4, 4), dtype=np.float64)
        Q[0, 0] = q00
        Q[0, 2] = q01
        Q[2, 0] = q01
        Q[2, 2] = q11

        Q[1, 1] = q00
        Q[1, 3] = q01
        Q[3, 1] = q01
        Q[3, 3] = q11

        self._P = F @ self._P @ F.T + Q
        self._last_time = float(t)
        return self.state

    def mahalanobis(
        self,
        z: tuple[float, float] | np.ndarray,
        R: np.ndarray | None = None,
    ) -> float:
        """Calculate normalized Mahalanobis distance of candidate measurement.

        Args:
            z: (pan_deg, tilt_deg) candidate measurement.
            R: Optional 2x2 measurement covariance matrix.

        Returns:
            Mahalanobis distance in standard deviations (sigmas).
        """
        if not self._initialized:
            return float("inf")

        # Innovation: shortest signed angular distance on pan
        y_pan = angular_diff_deg(float(z[0]), float(self._x[0]))
        y_tilt = float(z[1]) - float(self._x[1])
        y = np.array([y_pan, y_tilt], dtype=np.float64)

        H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=np.float64)
        meas_r = R if R is not None else self._default_R
        S = H @ self._P @ H.T + meas_r

        inv_S = np.linalg.inv(S)
        d2 = float(y.T @ inv_S @ y)
        return math.sqrt(max(0.0, d2))

    def update(
        self,
        z: tuple[float, float] | np.ndarray,
        t: float,
        R: np.ndarray | float | None = None,
    ) -> float:
        """Perform measurement update at time t.

        Args:
            z: (pan_deg, tilt_deg) measurement.
            t: Timestamp in seconds.
            R: Optional measurement covariance matrix or variance.

        Returns:
            Normalized Innovation Squared (NIS).
        """
        if not self._initialized:
            self.init(z, t)
            return 0.0

        if float(t) > self._last_time:
            self.predict(t)

        if R is None:
            R_mat = self._default_R
        elif isinstance(R, (int, float)):
            R_mat = np.diag([float(R), float(R)]).astype(np.float64)
        else:
            R_mat = np.asarray(R, dtype=np.float64)

        # Innovation y = z - Hx (with angular wrapping on pan)
        y_pan = angular_diff_deg(float(z[0]), float(self._x[0]))
        y_tilt = float(z[1]) - float(self._x[1])
        y = np.array([y_pan, y_tilt], dtype=np.float64)

        H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=np.float64)
        S = H @ self._P @ H.T + R_mat
        inv_S = np.linalg.inv(S)
        K = self._P @ H.T @ inv_S

        # State update
        self._x += K @ y
        self._x[0] = wrap_deg(float(self._x[0]))

        # Joseph-form covariance update: P = (I - KH) P (I - KH)^T + K R K^T
        I_KH = np.eye(4, dtype=np.float64) - K @ H
        self._P = I_KH @ self._P @ I_KH.T + K @ R_mat @ K.T
        # Enforce numerical symmetry
        self._P = 0.5 * (self._P + self._P.T)

        nis = float(y.T @ inv_S @ y)
        return nis

    def reset(self) -> None:
        """Reset filter to uninitialized state."""
        self._x.fill(0.0)
        self._P.fill(0.0)
        self._last_time = 0.0
        self._initialized = False
