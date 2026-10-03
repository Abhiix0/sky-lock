"""Per-frame JSONL/CSV logging and run record serialization."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, TextIO

from skylock.core.enums import Verdict
from skylock.core.types import StepResult
from skylock.metrics.status import RunMetrics


class FrameLogger:
    """Streams per-frame telemetry to JSON Lines (JSONL) format.

    Enforces the ground-truth firewall: ground truth attributes are only logged
    if present in StepResult.truth and are explicitly prefixed with 'gt_'.
    Missing values are emitted as JSON 'null'.
    """

    def __init__(self, file_or_path: str | Path | TextIO) -> None:
        """Initialize FrameLogger with a destination path or file-like object."""
        if isinstance(file_or_path, (str, Path)):
            self._path: Path | None = Path(file_or_path)
            self._file: TextIO = open(self._path, "w", encoding="utf-8")  # noqa: SIM115
            self._owns_file: bool = True
        else:
            self._path = None
            self._file = file_or_path
            self._owns_file = False

    def log(self, step: StepResult) -> None:
        """Write a single step result as a JSON line."""
        frame = step.frame
        output = step.output
        cmd = step.command
        truth = step.truth

        record: dict[str, Any] = {
            "index": frame.index,
            "t": float(frame.timestamp_s),
            "state": output.state.value,
            "estimate": (
                {
                    "px": float(output.estimate.px),
                    "py": float(output.estimate.py),
                    "pan_deg": float(output.estimate.pan_deg),
                    "tilt_deg": float(output.estimate.tilt_deg),
                }
                if output.estimate is not None
                else None
            ),
            "detections_count": len(output.detections),
            "latency_ms": float(output.latency_ms),
            "command": {
                "pan_rate_deg_s": float(cmd.pan_rate_deg_s),
                "tilt_rate_deg_s": float(cmd.tilt_rate_deg_s),
            },
        }

        # Include ground truth with 'gt_' prefix ONLY when truth is provided
        if truth is not None:
            record["gt_primary_px"] = (
                [float(truth.primary_px[0]), float(truth.primary_px[1])]
                if truth.primary_px is not None
                else None
            )
            record["gt_primary_visible"] = truth.primary_visible
            record["gt_boresight_error_px"] = (
                float(truth.boresight_error_px)
                if truth.boresight_error_px is not None
                else None
            )
            record["gt_pointing_pan_deg"] = float(truth.pointing.pan_deg)
            record["gt_pointing_tilt_deg"] = float(truth.pointing.tilt_deg)
            record["gt_disturbance_offset_px"] = [
                float(truth.disturbance_offset_px[0]),
                float(truth.disturbance_offset_px[1]),
            ]

        line = json.dumps(record, allow_nan=False)
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        """Flush and close underlying file if owned."""
        if self._owns_file and not self._file.closed:
            self._file.close()

    def __enter__(self) -> FrameLogger:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


class CSVFrameLogger:
    """Streams per-frame telemetry to CSV format.

    Enforces the ground-truth firewall: ground truth columns are only included
    if requested and are prefixed with 'gt_'. Missing values are written as empty strings.
    """

    # CSV column definitions
    _BASE_COLUMNS = [
        "index",
        "t",
        "state",
        "estimate_px",
        "estimate_py",
        "estimate_pan_deg",
        "estimate_tilt_deg",
        "detections_count",
        "latency_ms",
        "command_pan_rate_deg_s",
        "command_tilt_rate_deg_s",
    ]

    _GT_COLUMNS = [
        "gt_primary_px_x",
        "gt_primary_px_y",
        "gt_primary_visible",
        "gt_boresight_error_px",
        "gt_pointing_pan_deg",
        "gt_pointing_tilt_deg",
        "gt_disturbance_offset_px_x",
        "gt_disturbance_offset_px_y",
    ]

    def __init__(
        self,
        file_or_path: str | Path | TextIO,
        include_ground_truth: bool = False,
    ) -> None:
        """Initialize CSVFrameLogger with a destination path or file-like object.

        Args:
            file_or_path: Destination file path or writable text stream.
            include_ground_truth: If True, include gt_ prefixed columns for ground truth data.
        """
        if isinstance(file_or_path, (str, Path)):
            self._path: Path | None = Path(file_or_path)
            self._file: TextIO = open(self._path, "w", encoding="utf-8", newline="")  # noqa: SIM115
            self._owns_file: bool = True
        else:
            self._path = None
            self._file = file_or_path
            self._owns_file = False

        self._include_gt = include_ground_truth
        self._columns = (
            self._BASE_COLUMNS + self._GT_COLUMNS
            if include_ground_truth
            else self._BASE_COLUMNS
        )
        self._writer = csv.DictWriter(self._file, fieldnames=self._columns)
        self._writer.writeheader()
        self._file.flush()

    def log(self, step: StepResult) -> None:
        """Write a single step result as a CSV row."""
        frame = step.frame
        output = step.output
        cmd = step.command
        truth = step.truth

        row: dict[str, Any] = {
            "index": frame.index,
            "t": f"{frame.timestamp_s:.6f}",
            "state": output.state.value,
            "estimate_px": (
                f"{output.estimate.px:.3f}" if output.estimate is not None else ""
            ),
            "estimate_py": (
                f"{output.estimate.py:.3f}" if output.estimate is not None else ""
            ),
            "estimate_pan_deg": (
                f"{output.estimate.pan_deg:.6f}" if output.estimate is not None else ""
            ),
            "estimate_tilt_deg": (
                f"{output.estimate.tilt_deg:.6f}" if output.estimate is not None else ""
            ),
            "detections_count": len(output.detections),
            "latency_ms": f"{output.latency_ms:.3f}",
            "command_pan_rate_deg_s": f"{cmd.pan_rate_deg_s:.6f}",
            "command_tilt_rate_deg_s": f"{cmd.tilt_rate_deg_s:.6f}",
        }

        # Include ground truth columns if enabled
        if self._include_gt:
            if truth is not None:
                row["gt_primary_px_x"] = (
                    f"{truth.primary_px[0]:.3f}" if truth.primary_px is not None else ""
                )
                row["gt_primary_px_y"] = (
                    f"{truth.primary_px[1]:.3f}" if truth.primary_px is not None else ""
                )
                row["gt_primary_visible"] = str(truth.primary_visible)
                row["gt_boresight_error_px"] = (
                    f"{truth.boresight_error_px:.3f}"
                    if truth.boresight_error_px is not None
                    else ""
                )
                row["gt_pointing_pan_deg"] = f"{truth.pointing.pan_deg:.6f}"
                row["gt_pointing_tilt_deg"] = f"{truth.pointing.tilt_deg:.6f}"
                row["gt_disturbance_offset_px_x"] = (
                    f"{truth.disturbance_offset_px[0]:.3f}"
                )
                row["gt_disturbance_offset_px_y"] = (
                    f"{truth.disturbance_offset_px[1]:.3f}"
                )
            else:
                # No ground truth this frame, fill with empty strings
                for col in self._GT_COLUMNS:
                    row[col] = ""

        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        """Flush and close underlying file if owned."""
        if self._owns_file and not self._file.closed:
            self._file.close()

    def __enter__(self) -> CSVFrameLogger:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


def write_run_record(
    destination: str | Path | TextIO,
    metrics: RunMetrics,
    verdicts: dict[str, Verdict] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize full run record containing metrics, verdicts, and metadata.

    Args:
        destination: File path or writable file-like object.
        metrics: Finalized RunMetrics.
        verdicts: Optional requirements evaluation results.
        metadata: Optional run metadata (e.g. config snapshot, scenario id).

    Returns:
        The generated run record dictionary.
    """
    record: dict[str, Any] = {
        "metrics_version": metrics.metrics_version,
        "metrics": metrics.as_dict(),
        "verdicts": (
            {k: v.value for k, v in verdicts.items()}
            if verdicts is not None
            else None
        ),
        "metadata": metadata if metadata is not None else {},
    }

    content = json.dumps(record, indent=2, allow_nan=False)
    if isinstance(destination, (str, Path)):
        with open(destination, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        destination.write(content)
        destination.flush()

    return record


__all__ = ("FrameLogger", "CSVFrameLogger", "write_run_record")
