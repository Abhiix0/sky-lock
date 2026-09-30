"""Authoritative typed configuration models for SkyLock.

All configurations are defined as frozen dataclasses with slots and built-in validation.
No global or module-level default config instances are instantiated in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from skylock.config.validation import (
    ConfigError,
    validate_camera,
    validate_control,
    validate_detection,
    validate_disturbances,
    validate_gimbal,
    validate_kalman,
    validate_requirements,
    validate_root,
    validate_search,
    validate_target,
    validate_target_set,
    validate_tracking,
)


@dataclass(frozen=True, slots=True)
class CameraConfig:
    """Camera sensor hardware specification.

    PS_SPEC §1: FOV 4° horizontal × 3° vertical.
    PS_SPEC §2: 640×480 px, monochrome, minimum 30 Hz.
    """

    width: int = 640
    height: int = 480
    fov_h_deg: float = 4.0
    fov_v_deg: float = 3.0
    fps: float = 30.0
    monochrome: bool = True
    bit_depth: int = 8
    background_level: float = 20.0
    allow_below_spec_fps: bool = False

    def __post_init__(self) -> None:
        violations = validate_camera(self)
        if violations:
            raise ConfigError(violations)

    @property
    def ifov_h_deg(self) -> float:
        """Horizontal instantaneous field of view in degrees/pixel."""
        return self.fov_h_deg / self.width

    @property
    def ifov_v_deg(self) -> float:
        """Vertical instantaneous field of view in degrees/pixel."""
        return self.fov_v_deg / self.height

    @property
    def frame_period_s(self) -> float:
        """Frame duration period in seconds."""
        return 1.0 / self.fps

    @property
    def px_per_deg(self) -> float:
        """Horizontal pixel density (pixels/degree)."""
        return self.width / self.fov_h_deg


@dataclass(frozen=True, slots=True)
class GimbalConfig:
    """Pan/tilt gimbal physical parameters.

    PS_SPEC §3: Slew rate 5–10°/s, default 5°/s.
    """

    slew_rate_deg_s: float = 5.0
    max_slew_rate_deg_s: float = 10.0
    accel_deg_s2: float = 120.0
    pan_limit_deg: tuple[float, float] = (-45.0, 45.0)
    tilt_limit_deg: tuple[float, float] = (-30.0, 30.0)
    initial: tuple[float, float] = (0.0, 0.0)
    substeps: int = 4

    def __post_init__(self) -> None:
        violations = validate_gimbal(self)
        if violations:
            raise ConfigError(violations)


@dataclass(frozen=True, slots=True)
class LineMotion:
    kind: Literal["line"] = "line"
    speed_deg_s: float = 0.5
    heading_deg: float = 0.0


@dataclass(frozen=True, slots=True)
class CircleMotion:
    kind: Literal["circle"] = "circle"
    radius_deg: float = 1.0
    period_s: float = 10.0
    phase_rad: float = 0.0


@dataclass(frozen=True, slots=True)
class Figure8Motion:
    kind: Literal["figure8"] = "figure8"
    width_deg: float = 1.5
    height_deg: float = 1.0
    period_s: float = 12.0


@dataclass(frozen=True, slots=True)
class RandomMotion:
    kind: Literal["random"] = "random"
    speed_deg_s: float = 0.5
    correlation_s: float = 2.0
    bounds_deg: tuple[float, float, float, float] = (-1.5, 1.5, -1.0, 1.0)


MotionConfig = LineMotion | CircleMotion | Figure8Motion | RandomMotion


@dataclass(frozen=True, slots=True)
class TargetConfig:
    """Target optical beacon spot specification.

    PS_SPEC §4: 10×10 px default, 5×5 to 20×20 px range.
    PS_SPEC §5: Straight line, circular, figure-8, random motion models.
    """

    id: str = "target_0"
    size_px: int = 10
    shape: str = "disc"
    brightness: float = 220.0
    initial: str = "random"
    initial_pos_deg: tuple[float, float] = (0.0, 0.0)
    motion: MotionConfig = field(default_factory=LineMotion)
    visibility_windows: tuple[tuple[float, float], ...] = ()
    strict_spec: bool = True

    def __post_init__(self) -> None:
        violations = validate_target(self)
        if violations:
            raise ConfigError(violations)


@dataclass(frozen=True, slots=True)
class TargetSetConfig:
    count: int = 1
    targets: tuple[TargetConfig, ...] = field(default_factory=lambda: (TargetConfig(),))

    def __post_init__(self) -> None:
        violations = validate_target_set(self)
        if violations:
            raise ConfigError(violations)


@dataclass(frozen=True, slots=True)
class DetectionConfig:
    """Blob detector parameters for classical thresholding."""

    method: str = "classical"
    blur_sigma: float = 1.0
    threshold_k_sigma: float = 5.0
    abs_min_threshold: float = 25.0
    min_area_px: int = 6
    max_area_px: int = 900
    max_blobs: int = 8
    roi_margin_px: int = 48
    median_filter: bool = True

    def __post_init__(self) -> None:
        violations = validate_detection(self)
        if violations:
            raise ConfigError(violations)


@dataclass(frozen=True, slots=True)
class KalmanConfig:
    q_accel_deg_s2: float = 25.0
    r_meas_px: float = 1.0
    gate_sigma: float = 4.0

    def __post_init__(self) -> None:
        violations = validate_kalman(self)
        if violations:
            raise ConfigError(violations)


@dataclass(frozen=True, slots=True)
class SearchConfig:
    field_of_regard_deg: tuple[float, float] = (10.0, 8.0)
    raster_overlap: float = 0.2
    scan_rate_deg_s: float = 4.0

    def __post_init__(self) -> None:
        violations = validate_search(self)
        if violations:
            raise ConfigError(violations)


@dataclass(frozen=True, slots=True)
class TrackingConfig:
    """Target tracking and state machine parameters."""

    confirm_hits: int = 3
    confirm_window: int = 5
    acquire_timeout_s: float = 1.0
    lost_after_misses: int = 5
    coast_max_s: float = 0.5
    reacquire_timeout_s: float = 1.0
    reacquire_radius_deg: float = 1.0
    association_gate_px: float = 30.0
    kalman: KalmanConfig = field(default_factory=KalmanConfig)
    search: SearchConfig = field(default_factory=SearchConfig)

    def __post_init__(self) -> None:
        violations = validate_tracking(self)
        if violations:
            raise ConfigError(violations)


@dataclass(frozen=True, slots=True)
class ControlConfig:
    """Gimbal pointing controller parameters."""

    kp: float = 4.0
    ki: float = 0.5
    kd: float = 0.2
    kff: float = 1.0
    d_filter_alpha: float = 0.2
    integral_clamp: float = 8.0
    deadband_px: float = 1.0
    latency_frames: int = 1
    mode: str = "AUTO"

    def __post_init__(self) -> None:
        violations = validate_control(self)
        if violations:
            raise ConfigError(violations)


@dataclass(frozen=True, slots=True)
class SaltPepperConfig:
    enabled: bool = False
    density: float = 0.0


@dataclass(frozen=True, slots=True)
class GaussianConfig:
    enabled: bool = False
    sigma_levels: float = 0.0


@dataclass(frozen=True, slots=True)
class PoissonConfig:
    enabled: bool = False
    photon_scale: float = 1.0


@dataclass(frozen=True, slots=True)
class JitterConfig:
    enabled: bool = False
    max_px_frame: float = 0.0
    correlation: float = 0.5


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    enabled: bool = False
    kind: str = "linear"
    velocity_px_frame: float | tuple[float, float] = 0.0
    max_px_frame: float = 0.0


@dataclass(frozen=True, slots=True)
class AtmosphereConfig:
    enabled: bool = False
    mode: str = "clear"
    strength: float = 0.0


@dataclass(frozen=True, slots=True)
class BlurConfig:
    enabled: bool = False
    sigma_px: float = 0.0


@dataclass(frozen=True, slots=True)
class DisturbanceConfig:
    """Environmental and platform disturbance components.

    PS_SPEC §6: Noise σ max 20, jitter ±20 px/frame, platform motion ±20 px/frame.
    """

    salt_pepper: SaltPepperConfig = field(default_factory=SaltPepperConfig)
    gaussian: GaussianConfig = field(default_factory=GaussianConfig)
    poisson: PoissonConfig = field(default_factory=PoissonConfig)
    camera_jitter: JitterConfig = field(default_factory=JitterConfig)
    platform: PlatformConfig = field(default_factory=PlatformConfig)
    atmosphere: AtmosphereConfig = field(default_factory=AtmosphereConfig)
    blur: BlurConfig = field(default_factory=BlurConfig)

    def __post_init__(self) -> None:
        violations = validate_disturbances(self)
        if violations:
            raise ConfigError(violations)


@dataclass(frozen=True, slots=True)
class InputConfig:
    kind: str = "simulation"
    mp4_path: str = ""
    mp4_assumed_fov_h_deg: float = 4.0
    loop: bool = False


@dataclass(frozen=True, slots=True)
class RequirementsConfig:
    """Authoritative performance evaluation requirements.

    PS_SPEC §7:
    - Acquisition Time: <= 2.0 s
    - Tracking Error: <= 10.0 px (RMS)
    - Target Loss Rate: < 0.05 (5%)
    - Re-acquisition Time: <= 1.0 s
    - Processing Cadence: >= 20.0 FPS
    """

    acquisition_max_s: float = 2.0
    tracking_error_px_max: float = 10.0
    tracking_error_statistic: str = "rms"
    target_loss_rate_max: float = 0.05
    reacquisition_max_s: float = 1.0
    processing_fps_min: float = 20.0
    lock_radius_px: float = 10.0

    def __post_init__(self) -> None:
        violations = validate_requirements(self)
        if violations:
            raise ConfigError(violations)


@dataclass(frozen=True, slots=True)
class SkyLockConfig:
    """Root configuration holding all sub-system configs and run seed."""

    camera: CameraConfig = field(default_factory=CameraConfig)
    target: TargetSetConfig = field(default_factory=TargetSetConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    gimbal: GimbalConfig = field(default_factory=GimbalConfig)
    disturbances: DisturbanceConfig = field(default_factory=DisturbanceConfig)
    input: InputConfig = field(default_factory=InputConfig)
    requirements: RequirementsConfig = field(default_factory=RequirementsConfig)
    seed: int = 42

    def __post_init__(self) -> None:
        violations = validate_root(self)
        if violations:
            raise ConfigError(violations)
