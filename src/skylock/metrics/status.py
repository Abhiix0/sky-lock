"""Metric data structures, status contracts, and consolidated run metrics."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from skylock.core.enums import MetricStatus


@dataclass(frozen=True, slots=True)
class Metric[T]:
    """Performance metric wrapper carrying explicit measurement status and reason.

    Invariant:
        self.value is None <==> self.status != MetricStatus.MEASURED
    """

    value: T | None
    status: MetricStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status == MetricStatus.MEASURED:
            if self.value is None:
                raise ValueError("Metric value cannot be None when status is MEASURED")
            if isinstance(self.value, float) and math.isnan(self.value):
                raise ValueError("Metric value cannot be NaN when status is MEASURED")
        else:
            if self.value is not None:
                raise ValueError(
                    f"Metric value must be None when status is {self.status.value}, "
                    f"got {self.value!r}"
                )

    @classmethod
    def measured(cls, value: T) -> Metric[T]:
        """Construct a successfully measured metric with value."""
        if value is None:
            raise ValueError("measured() requires a non-None value")
        if isinstance(value, float) and math.isnan(value):
            raise ValueError("measured() cannot accept NaN")
        return cls(value=value, status=MetricStatus.MEASURED, reason=None)

    @classmethod
    def not_run(cls, reason: str = "Metric calculation not run") -> Metric[T]:
        """Construct an uncalculated metric."""
        return cls(value=None, status=MetricStatus.NOT_RUN, reason=reason)

    @classmethod
    def not_acquired(cls, reason: str = "Target not acquired") -> Metric[T]:
        """Construct a metric that was not acquired."""
        return cls(value=None, status=MetricStatus.NOT_ACQUIRED, reason=reason)

    @classmethod
    def failed(cls, reason: str = "Metric calculation failed") -> Metric[T]:
        """Construct a metric whose calculation failed or aborted."""
        return cls(value=None, status=MetricStatus.FAILED, reason=reason)

    def as_dict(self) -> dict[str, Any]:
        """Serialize metric representation for JSON emission."""
        val = self.value
        val_out: Any
        if val is not None and hasattr(val, "as_dict"):
            val_out = val.as_dict()
        elif val is not None and is_dataclass(val) and not isinstance(val, type):
            val_out = asdict(val)
        else:
            val_out = val
        return {
            "value": val_out,
            "status": self.status.value,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ErrorStats:
    """Summary statistics for spatial error distributions (pixels or degrees)."""

    mean: float
    rms: float
    p95: float
    max: float
    n: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "mean": self.mean,
            "rms": self.rms,
            "p95": self.p95,
            "max": self.max,
            "n": self.n,
        }


@dataclass(frozen=True, slots=True)
class LatencyStats:
    """Summary statistics for processing latency distributions (milliseconds)."""

    mean: float
    p50: float
    p95: float
    max: float
    n: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "mean": self.mean,
            "p50": self.p50,
            "p95": self.p95,
            "max": self.max,
            "n": self.n,
        }


@dataclass(frozen=True, slots=True)
class ReacquisitionEvent:
    """Individual target reacquisition event record."""

    duration_s: float | None
    basis: str  # "ground_truth" or "tracker_only"
    success: bool
    t_start: float
    t_end: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "duration_s": self.duration_s,
            "basis": self.basis,
            "success": self.success,
            "t_start": self.t_start,
            "t_end": self.t_end,
        }


@dataclass(frozen=True, slots=True)
class ReacquisitionSummary:
    """Consolidated statistics across all target reacquisition events."""

    events: tuple[ReacquisitionEvent, ...]
    mean_s: float
    max_s: float
    n: int
    basis: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "events": [e.as_dict() for e in self.events],
            "mean_s": self.mean_s,
            "max_s": self.max_s,
            "n": self.n,
            "basis": self.basis,
        }


@dataclass(frozen=True, slots=True)
class MissedFrames:
    """Accounting of missed processing deadlines and dropped feed frames."""

    processing_missed: int
    source_dropped: int
    total_frames: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "processing_missed": self.processing_missed,
            "source_dropped": self.source_dropped,
            "total_frames": self.total_frames,
        }


@dataclass(frozen=True, slots=True)
class RunMetrics:
    """Consolidated performance metrics for a tracking execution run."""

    metrics_version: str = "1"
    total_frames: int = 0
    observable_duration_s: float = 0.0

    acquisition_time_from_start_s: Metric[float] = field(default_factory=Metric.not_run)
    acquisition_time_from_observable_s: Metric[float] = field(default_factory=Metric.not_run)
    successful_acquisition: Metric[bool] = field(default_factory=Metric.not_run)

    tracking_error_px: Metric[ErrorStats] = field(default_factory=Metric.not_run)
    pointing_error_px: Metric[ErrorStats] = field(default_factory=Metric.not_run)
    centering_error_px: Metric[ErrorStats] = field(default_factory=Metric.not_run)

    reacquisition_time_s: Metric[ReacquisitionSummary] = field(default_factory=Metric.not_run)
    successful_reacquisition: Metric[bool] = field(default_factory=Metric.not_run)

    target_loss_rate: Metric[float] = field(default_factory=Metric.not_run)
    lock_retention: Metric[float] = field(default_factory=Metric.not_run)

    detection_rate: Metric[float] = field(default_factory=Metric.not_run)
    detection_present_rate: Metric[float] = field(default_factory=Metric.not_run)

    fps_pipeline: Metric[float] = field(default_factory=Metric.not_run)
    fps_wall: Metric[float] = field(default_factory=Metric.not_run)
    latency_ms: Metric[LatencyStats] = field(default_factory=Metric.not_run)
    missed_frames: Metric[MissedFrames] = field(default_factory=Metric.not_run)

    def as_dict(self) -> dict[str, Any]:
        """Serialize run metrics to a nested dictionary for JSON reporting."""
        return {
            "metrics_version": self.metrics_version,
            "total_frames": self.total_frames,
            "observable_duration_s": self.observable_duration_s,
            "acquisition_time_from_start_s": self.acquisition_time_from_start_s.as_dict(),
            "acquisition_time_from_observable_s": self.acquisition_time_from_observable_s.as_dict(),
            "successful_acquisition": self.successful_acquisition.as_dict(),
            "tracking_error_px": self.tracking_error_px.as_dict(),
            "pointing_error_px": self.pointing_error_px.as_dict(),
            "centering_error_px": self.centering_error_px.as_dict(),
            "reacquisition_time_s": self.reacquisition_time_s.as_dict(),
            "successful_reacquisition": self.successful_reacquisition.as_dict(),
            "target_loss_rate": self.target_loss_rate.as_dict(),
            "lock_retention": self.lock_retention.as_dict(),
            "detection_rate": self.detection_rate.as_dict(),
            "detection_present_rate": self.detection_present_rate.as_dict(),
            "fps_pipeline": self.fps_pipeline.as_dict(),
            "fps_wall": self.fps_wall.as_dict(),
            "latency_ms": self.latency_ms.as_dict(),
            "missed_frames": self.missed_frames.as_dict(),
        }
