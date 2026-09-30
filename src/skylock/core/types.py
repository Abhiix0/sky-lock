"""Core data contracts, frame structures, and pipeline interfaces.

All data structures are immutable dataclasses with slots.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import numpy as np

from skylock.core.enums import ControlIntentMode, TrackState
from skylock.core.errors import FrameError


@dataclass(frozen=True, slots=True)
class Pointing:
    """Gimbal encoder line-of-sight angles in degrees."""

    pan_deg: float
    tilt_deg: float


@dataclass(frozen=True, slots=True)
class Frame:
    """Single camera sensor frame.

    Ground-truth data is strictly forbidden from this structure.
    """

    image: np.ndarray
    index: int
    timestamp_s: float
    source_id: str
    pointing: Pointing | None = None
    meta: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.image, np.ndarray):
            raise FrameError(f"image must be a numpy.ndarray, got {type(self.image)}")
        if self.image.ndim != 2:
            raise FrameError(f"image must be 2-D monochrome (H, W), got shape {self.image.shape}")
        if self.image.dtype != np.uint8:
            raise FrameError(f"image must have dtype uint8, got {self.image.dtype}")
        # Enforce immutability of sensor frame buffer
        self.image.flags.writeable = False


@dataclass(frozen=True, slots=True)
class Detection:
    """Single blob detection in pixel space."""

    cx: float
    cy: float
    area_px: float
    peak: float
    snr: float
    bbox: tuple[int, int, int, int]  # (x, y, w, h)


@dataclass(frozen=True, slots=True)
class Candidate:
    """Track candidate undergoing temporal confirmation."""

    id: int
    cx: float
    cy: float
    age: int
    hits: int
    misses: int
    confirmed: bool
    score: float


@dataclass(frozen=True, slots=True)
class TargetEstimate:
    """Filtered target kinematic state estimate."""

    pan_deg: float
    tilt_deg: float
    pan_rate: float
    tilt_rate: float
    px: float
    py: float
    sigma_deg: float
    from_measurement: bool


@dataclass(frozen=True, slots=True)
class ControlIntent:
    """Desired control intent from tracking state machine."""

    mode: ControlIntentMode
    setpoint_pan_deg: float = 0.0
    setpoint_tilt_deg: float = 0.0
    image_error_px: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class ControlCommand:
    """Commanded gimbal motor angular rates in deg/s."""

    pan_rate_deg_s: float
    tilt_rate_deg_s: float


@dataclass(frozen=True, slots=True)
class PipelineOutput:
    """Comprehensive output produced by TrackingPipeline for a single frame."""

    frame_index: int
    timestamp_s: float
    state: TrackState
    estimate: TargetEstimate | None
    detections: tuple[Detection, ...]
    selected: Candidate | None
    intent: ControlIntent
    latency_ms: float


@dataclass(frozen=True, slots=True)
class StateEvent:
    """State transition event emitted by the tracking state machine."""

    timestamp_s: float
    from_state: TrackState
    to_state: TrackState
    reason: str

    @property
    def t(self) -> float:
        return self.timestamp_s


@dataclass(frozen=True, slots=True)
class TargetTruth:
    """Ground truth state for a single simulated target."""

    id: str
    az_deg: float
    el_deg: float
    px: float
    py: float
    visible: bool
    in_fov: bool


@dataclass(frozen=True, slots=True)
class GroundTruthSample:
    """METRICS ONLY - never import into vision/tracking/control.

    Delivered exclusively to MetricsCollector via SimulationSource.read_with_truth().
    """

    frame_index: int
    timestamp_s: float
    targets: tuple[TargetTruth, ...]
    primary_px: tuple[float, float] | None
    primary_visible: bool
    boresight_error_px: float | None
    pointing: Pointing
    disturbance_offset_px: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True, slots=True)
class StepResult:
    """Comprehensive output produced by a single Session step.

    Passed to callers and metrics collectors; truth is passed through untouched
    and never inspected or processed by the tracking pipeline or controller.
    """

    frame: Frame
    output: PipelineOutput
    command: ControlCommand
    truth: GroundTruthSample | None = None
