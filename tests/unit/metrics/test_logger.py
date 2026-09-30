"""Unit tests for FrameLogger and RunRecord writer."""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

import numpy as np

from skylock.config.models import RequirementsConfig
from skylock.core.enums import ControlIntentMode, TrackState, Verdict
from skylock.core.types import (
    ControlCommand,
    ControlIntent,
    Frame,
    GroundTruthSample,
    PipelineOutput,
    Pointing,
    StepResult,
    TargetEstimate,
    TargetTruth,
)
from skylock.metrics.logger import FrameLogger, write_run_record
from skylock.metrics.requirements import evaluate
from skylock.metrics.status import Metric, RunMetrics


def _build_step(with_gt: bool = True) -> StepResult:
    frame = Frame(
        image=np.zeros((480, 640), dtype=np.uint8),
        index=0,
        timestamp_s=0.0,
        source_id="logger_test",
        pointing=Pointing(1.0, 2.0),
    )
    estimate = TargetEstimate(
        pan_deg=1.0,
        tilt_deg=2.0,
        pan_rate=0.0,
        tilt_rate=0.0,
        px=320.0,
        py=240.0,
        sigma_deg=0.05,
        from_measurement=True,
    )
    output = PipelineOutput(
        frame_index=0,
        timestamp_s=0.0,
        state=TrackState.TRACK,
        estimate=estimate,
        detections=(),
        selected=None,
        intent=ControlIntent(mode=ControlIntentMode.TRACK),
        latency_ms=12.5,
    )
    cmd = ControlCommand(pan_rate_deg_s=0.5, tilt_rate_deg_s=-0.5)
    truth = (
        GroundTruthSample(
            frame_index=0,
            timestamp_s=0.0,
            targets=(
                TargetTruth(
                    id="t1",
                    az_deg=1.0,
                    el_deg=2.0,
                    px=322.0,
                    py=241.0,
                    visible=True,
                    in_fov=True,
                ),
            ),
            primary_px=(322.0, 241.0),
            primary_visible=True,
            boresight_error_px=2.236,
            pointing=Pointing(1.0, 2.0),
            disturbance_offset_px=(0.1, -0.1),
        )
        if with_gt
        else None
    )
    return StepResult(frame=frame, output=output, command=cmd, truth=truth)


def test_frame_logger_with_ground_truth() -> None:
    """FrameLogger writes JSON line with gt_ prefixed fields when truth is present."""
    stream = io.StringIO()
    logger = FrameLogger(stream)

    step = _build_step(with_gt=True)
    logger.log(step)

    content = stream.getvalue().strip()
    record = json.loads(content)

    assert record["index"] == 0
    assert record["state"] == "TRACK"
    assert record["estimate"]["px"] == 320.0
    assert record["latency_ms"] == 12.5
    assert record["command"]["pan_rate_deg_s"] == 0.5

    # Ground truth fields present with gt_ prefix
    assert record["gt_primary_px"] == [322.0, 241.0]
    assert record["gt_primary_visible"] is True
    assert record["gt_boresight_error_px"] == 2.236
    assert record["gt_disturbance_offset_px"] == [0.1, -0.1]


def test_frame_logger_without_ground_truth() -> None:
    """FrameLogger omits gt_ fields entirely when truth is None."""
    stream = io.StringIO()
    logger = FrameLogger(stream)

    step = _build_step(with_gt=False)
    logger.log(step)

    content = stream.getvalue().strip()
    record = json.loads(content)

    assert record["index"] == 0
    assert record["state"] == "TRACK"
    # No gt_ fields should exist
    assert not any(k.startswith("gt_") for k in record)


def test_frame_logger_null_handling() -> None:
    """When estimate is None, estimate emits null."""
    stream = io.StringIO()
    logger = FrameLogger(stream)

    step = _build_step(with_gt=False)
    # Clear estimate
    output_no_est = PipelineOutput(
        frame_index=0,
        timestamp_s=0.0,
        state=TrackState.SEARCH,
        estimate=None,
        detections=(),
        selected=None,
        intent=ControlIntent(mode=ControlIntentMode.HOLD),
        latency_ms=5.0,
    )
    step_no_est = StepResult(
        frame=step.frame,
        output=output_no_est,
        command=step.command,
        truth=None,
    )
    logger.log(step_no_est)

    content = stream.getvalue().strip()
    assert '"estimate": null' in content


def test_write_run_record() -> None:
    """write_run_record produces valid JSON containing metrics, verdicts, and metadata."""
    metrics = RunMetrics(
        metrics_version="1",
        total_frames=10,
        acquisition_time_from_start_s=Metric.measured(0.5),
        acquisition_time_from_observable_s=Metric.not_run("No GT"),
    )
    verdicts = evaluate(metrics, RequirementsConfig())

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "run_record.json"
        record = write_run_record(
            destination=path,
            metrics=metrics,
            verdicts=verdicts,
            metadata={"scenario": "test_scenario"},
        )

        assert record["metrics_version"] == "1"
        assert record["metadata"]["scenario"] == "test_scenario"
        assert record["verdicts"]["overall"] in (Verdict.INDETERMINATE.value, Verdict.FAIL.value)

        # File readback
        saved_text = path.read_text(encoding="utf-8")
        parsed = json.loads(saved_text)
        assert parsed["metrics_version"] == "1"
        assert "NaN" not in saved_text
