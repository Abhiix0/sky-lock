"""
Authoritative configuration for the Sky Lock tracking system.

All values are aligned to docs/PS_SPEC.md (DOC-PS-SPEC-001).
This module is the single source of truth for runtime parameters.

JS reference: src/tracking/config.js
"""

from __future__ import annotations

from dataclasses import dataclass

# ============================================================
# CAMERA CONFIGURATION
# ============================================================


@dataclass(frozen=True)
class CameraConfig:
    """Camera and gimbal hardware parameters.

    PS_SPEC §1: FOV 4° horizontal × 3° vertical.
    PS_SPEC §2: 640×480, ≥30 Hz.
    PS_SPEC §3: Slew 5–10°/s, default 5°/s.
    """

    fov_h_deg: float = 4.0
    """Horizontal field of view in degrees (PS_SPEC §1)."""

    fov_v_deg: float = 3.0
    """Vertical field of view in degrees (PS_SPEC §1)."""

    width: int = 640
    """Sensor width in pixels (PS_SPEC §2)."""

    height: int = 480
    """Sensor height in pixels (PS_SPEC §2)."""

    feed_rate_hz: float = 30.0
    """Camera feed update rate in Hz (PS_SPEC §2: ≥30 Hz)."""

    max_slew_rate_deg_s: float = 5.0
    """Maximum gimbal slew rate in deg/s (PS_SPEC §3: default 5°/s)."""

    max_slew_accel_deg_s2: float = 120.0
    """Maximum gimbal slew acceleration in deg/s² (servo dynamics)."""

    pan_limit_deg: float = 180.0
    """Maximum pan angle in degrees (±)."""

    tilt_limit_deg: float = 90.0
    """Maximum tilt angle in degrees (±)."""

    pan_wrap: bool = True
    """Whether pan angle wraps across ±180°."""

    sim_step_hz: float = 120.0
    """Fixed simulation clock frequency in Hz."""

    @property
    def fov_deg(self) -> float:
        """Vertical FOV for backward compatibility with pinhole projection."""
        return self.fov_v_deg

    @property
    def dt(self) -> float:
        """Simulation timestep in seconds."""
        return 1.0 / self.sim_step_hz


# ============================================================
# KALMAN TRACKER CONFIGURATION
# ============================================================


@dataclass(frozen=True)
class KalmanConfig:
    """Kalman filter tuning parameters.

    Constant-velocity model with discrete white-noise acceleration.
    """

    q_accel_deg_s2: float = 25.0
    """Process noise acceleration variance (deg/s²)²."""

    r_meas_deg: float = 0.1
    """Measurement noise standard deviation in degrees."""

    gate_threshold_sigma: float = 4.0
    """Innovation gating threshold in standard deviations."""


# ============================================================
# CONTROLLER CONFIGURATION
# ============================================================


@dataclass(frozen=True)
class ControllerConfig:
    """PID controller with feed-forward and anti-windup.

    JS reference: CONTROLLER_CONFIG in config.js.
    """

    kp: float = 4.0
    """Proportional gain."""

    ki: float = 0.5
    """Integral gain."""

    kd: float = 0.2
    """Derivative gain."""

    kff: float = 1.0
    """Feed-forward velocity gain."""

    d_filter_alpha: float = 0.2
    """Low-pass filter smoothing for derivative term [0, 1]."""

    integral_clamp_deg_s: float = 8.0
    """Anti-windup clamp on integral accumulation (deg·s)."""


# ============================================================
# DETECTOR CONFIGURATION
# ============================================================


@dataclass(frozen=True)
class DetectorConfig:
    """Beacon blob detector parameters.

    PS_SPEC §4: Spot size 5×5 to 20×20 px, default 10×10 px.
    """

    mode: str = "chroma"
    """Detection mode: 'chroma' or 'luma'."""

    luma_threshold: int = 200
    """Intensity threshold for luma mode [0, 255]."""

    chroma_threshold: int = 90
    """Chroma threshold: min(R, B) - G [0, 255]."""

    min_area_px: int = 2
    """Minimum connected component area in pixels."""

    max_area_px: int = 900
    """Maximum connected component area in pixels."""

    max_blobs: int = 8
    """Maximum number of detected blobs returned."""

    roi_margin_px: int = 40
    """Margin around predicted position for ROI tracking."""


# ============================================================
# TRACKING STATE MACHINE & SCAN CONFIGURATION
# ============================================================


@dataclass(frozen=True)
class TrackingConfig:
    """State machine and scan pattern parameters.

    PS_SPEC §7: Acquisition ≤2s, re-acquisition ≤1s, loss <5%.
    """

    overlap: float = 0.2
    """Overlap fraction between adjacent scan FOVs [0, 1]."""

    tilt_scan_limit_deg: float = 55.0
    """Elevation coverage limit in degrees (±)."""

    scan_rate_deg_s: float = 4.0
    """Scanning slew rate in deg/s (must be ≤ max_slew_rate)."""

    reacquire_max_radius_deg: float = 10.0
    """Maximum search radius for spiral reacquisition in degrees."""

    min_snr_search: float = 3.0
    """Minimum SNR threshold to trigger acquisition from search."""

    acquire_confirm_frames: int = 3
    """Consecutive confirmed detections to enter TRACK."""

    acquire_timeout_sec: float = 1.0
    """Timeout in seconds before aborting unconfirmed acquire."""

    lost_miss_frames: int = 5
    """Consecutive missed frames before entering LOST/coasting."""

    coast_max_sec: float = 10.0
    """Maximum duration to coast on prediction before REACQUIRE."""

    lock_radius_px: float = 10.0
    """Tracking error threshold in pixels (PS_SPEC §7: ≤10 px)."""


# ============================================================
# BEACON CONFIGURATION
# ============================================================


@dataclass(frozen=True)
class BeaconConfig:
    """Optical beacon spot parameters.

    PS_SPEC §4: Spot 10×10 px default, 5–20 range.
    """

    spot_size_px: int = 10
    """Default beacon spot size in pixels (PS_SPEC §4)."""

    spot_min_px: int = 5
    """Minimum spot size in pixels."""

    spot_max_px: int = 20
    """Maximum spot size in pixels."""

    brightness: float = 1.0
    """Brightness multiplier [0, 1]."""

    blink_hz: float = 0.0
    """Blink frequency in Hz (0 = steady)."""

    blink_duty: float = 0.5
    """Blink duty cycle [0, 1]."""


# ============================================================
# BEACON CODING & IDENTIFICATION (Phase 3B)
# ============================================================


@dataclass(frozen=True)
class BeaconCodeConfig:
    """Blink-code beacon identification parameters."""

    bits: str = "10110010"
    """Beacon blink code bit pattern."""

    bit_period_sec: float = 0.1
    """Duration of one bit in seconds."""

    samples_per_bit: int = 3
    """Camera frames per bit (at 30 Hz feed → 3 frames/bit)."""

    mode: str = "steady"
    """Beacon mode: 'steady' | 'code'."""


@dataclass(frozen=True)
class IdConfig:
    """Beacon identification and candidate gating parameters."""

    id_threshold: float = 0.7
    """Matched filter score threshold for confirmation."""

    id_confirm_frames: int = 3
    """Consecutive frames above threshold to confirm ID."""

    history_window_frames: int = 48
    """Sliding window size: 2 × code_length_in_frames."""

    gate_initial_px: float = 35.0
    """Initial spatial gate radius in pixels."""

    gate_growth_px_per_frame: float = 3.0
    """Gate expansion rate in pixels/frame during missed detections."""

    gate_max_px: float = 90.0
    """Maximum gate radius in pixels."""

    max_miss_frames: int = 6
    """Maximum consecutive missed frames before dropping candidate."""

    intensity_threshold: float = 40.0
    """Minimum intensity to register a blink sample."""

    association_gate_px: float = 25.0
    """Data association gate radius in pixels."""


# ============================================================
# DISTURBANCE PRESETS
# ============================================================


@dataclass(frozen=True)
class DisturbanceConfig:
    """Environmental disturbance parameters.

    PS_SPEC §6: Noise σ max 20 px, jitter ±20 px/frame.
    """

    name: str = "Off"
    wander_rms_px: float = 0.0
    wander_corner_hz: float = 2.0
    scintillation_sigma: float = 0.0
    jitter_rms_deg: float = 0.0
    vibration_hz: float = 10.0
    noise_sigma: float = 0.0
    hot_pixels_count: int = 0
    blur_radius_px: float = 0.0
    drop_probability: float = 0.0


DISTURBANCE_PRESETS: dict[str, DisturbanceConfig] = {
    "OFF": DisturbanceConfig(name="Off"),
    "LOW": DisturbanceConfig(
        name="Low",
        wander_rms_px=1.0,
        scintillation_sigma=0.15,
        jitter_rms_deg=0.04,
        noise_sigma=4.0,
        hot_pixels_count=2,
        blur_radius_px=1.0,
        drop_probability=0.02,
    ),
    "MED": DisturbanceConfig(
        name="Med",
        wander_rms_px=2.5,
        scintillation_sigma=0.35,
        jitter_rms_deg=0.15,
        noise_sigma=10.0,
        hot_pixels_count=6,
        blur_radius_px=2.0,
        drop_probability=0.05,
    ),
    "HIGH": DisturbanceConfig(
        name="High",
        wander_rms_px=6.0,
        wander_corner_hz=3.0,
        scintillation_sigma=0.75,
        jitter_rms_deg=0.48,
        vibration_hz=12.0,
        noise_sigma=20.0,  # PS_SPEC §6: max 20 px (was 22 in JS)
        hot_pixels_count=18,
        blur_radius_px=3.0,
        drop_probability=0.18,
    ),
}


# ============================================================
# DEFAULT INSTANCES
# ============================================================

CAMERA = CameraConfig()
KALMAN = KalmanConfig()
CONTROLLER = ControllerConfig()
DETECTOR = DetectorConfig()
TRACKING = TrackingConfig()
BEACON = BeaconConfig()
BEACON_CODE = BeaconCodeConfig()
ID_CONFIG = IdConfig(association_gate_px=25.0)
