"""SkyLock metrics evaluation, logging, and performance contracts."""

from skylock.metrics.calculators import (
    calculate_acquisition_time,
    calculate_centering_error,
    calculate_detection_rates,
    calculate_error_stats,
    calculate_fps_and_latency,
    calculate_lock_retention,
    calculate_pointing_error,
    calculate_reacquisition,
    calculate_target_loss_rate,
    calculate_tracking_error,
)
from skylock.metrics.collector import MetricsCollector
from skylock.metrics.logger import FrameLogger, write_run_record
from skylock.metrics.requirements import evaluate
from skylock.metrics.sidecar import GroundTruthSidecar
from skylock.metrics.status import (
    ErrorStats,
    LatencyStats,
    Metric,
    MissedFrames,
    ReacquisitionEvent,
    ReacquisitionSummary,
    RunMetrics,
)

__all__ = (
    "ErrorStats",
    "FrameLogger",
    "GroundTruthSidecar",
    "LatencyStats",
    "Metric",
    "MetricsCollector",
    "MissedFrames",
    "ReacquisitionEvent",
    "ReacquisitionSummary",
    "RunMetrics",
    "calculate_acquisition_time",
    "calculate_centering_error",
    "calculate_detection_rates",
    "calculate_error_stats",
    "calculate_fps_and_latency",
    "calculate_lock_retention",
    "calculate_pointing_error",
    "calculate_reacquisition",
    "calculate_target_loss_rate",
    "calculate_tracking_error",
    "evaluate",
    "write_run_record",
)
