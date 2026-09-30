"""Session execution engine orchestrating sensor, pipeline, controller, and gimbal."""

from __future__ import annotations

import collections
from typing import Any

from skylock.config.models import SkyLockConfig
from skylock.control.controller import PointingController
from skylock.core.enums import InputKind
from skylock.core.interfaces import FrameSource
from skylock.core.pipeline import TrackingPipeline
from skylock.core.types import ControlCommand, Frame, GroundTruthSample, StepResult


class Session:
    """Execution session closing the loop between sensor input, tracking, and pointing control.

    Enforces the ground-truth firewall:
    - GroundTruthSample is captured from simulation and passed untouched to StepResult.truth.
    - Pipeline and controller receive only sensor frames and telemetry.
    - Control commands are delayed by `control.latency_frames` before being applied to the gimbal.
    """

    def __init__(
        self,
        config: SkyLockConfig,
        source: FrameSource | None = None,
        pipeline: TrackingPipeline | None = None,
        controller: PointingController | None = None,
        collector: Any | None = None,
    ) -> None:
        """Initialize Session.

        Args:
            config: Root system configuration.
            source: Video or simulation frame source. If None, built via factory.
            pipeline: Vision and tracking pipeline. If None, built via factory.
            controller: Gimbal pointing controller. If None, built via factory.
            collector: Optional metrics collector receiving step results.
        """
        self.config = config

        if source is None or pipeline is None or controller is None:
            from skylock.app.factory import create_session_components

            src, pip, ctrl = create_session_components(config)
            source = source if source is not None else src
            pipeline = pipeline if pipeline is not None else pip
            controller = controller if controller is not None else ctrl

        self.source = source
        self.pipeline = pipeline
        self.controller = controller
        self.collector: Any | None = collector

        self._latency_frames: int = config.control.latency_frames
        self._cmd_queue: collections.deque[ControlCommand] = collections.deque(
            [ControlCommand(0.0, 0.0) for _ in range(self._latency_frames)]
        )

    @property
    def latency_frames(self) -> int:
        """Configured control delay in frames."""
        return self._latency_frames

    def reset(self) -> None:
        """Reset source, pipeline, controller, and command latency buffer to initial state."""
        self.source.reset()
        self.pipeline.reset()
        self.controller.reset()
        self._cmd_queue = collections.deque(
            [ControlCommand(0.0, 0.0) for _ in range(self._latency_frames)]
        )
        if self.collector is not None and hasattr(self.collector, "reset"):
            self.collector.reset()

    def step(self) -> StepResult | None:
        """Execute one simulation and control step.

        Execution order:
        1. Read frame from source (captures GroundTruthSample if simulation).
        2. Process frame through TrackingPipeline (image-only, no truth).
        3. Step PointingController using intent, estimate, and gimbal telemetry.
        4. Apply control command to gimbal (only if SIMULATION), delayed by latency_frames.
        5. Package and return StepResult, passing truth untouched for external evaluation.

        Returns:
            StepResult containing frame, output, command, and truth (or None if stream ended).
        """
        # 1. Read frame
        truth: GroundTruthSample | None = None
        if hasattr(self.source, "read_with_truth"):
            try:
                frame, truth = self.source.read_with_truth()
            except RuntimeError:
                return None
        else:
            frame_opt: Frame | None = self.source.read()
            if frame_opt is None:
                return None
            frame = frame_opt

        if frame is None:
            return None

        # 2. Process frame through pipeline (image-only)
        output = self.pipeline.process(frame)

        # 3. Step controller (image-space error, estimate, and gimbal pointing)
        fps = self.source.fps if getattr(self.source, "fps", 0.0) > 0.0 else self.config.camera.fps
        dt = 1.0 / fps
        cmd = self.controller.step(
            intent=output.intent,
            estimate=output.estimate,
            pointing=frame.pointing,
            dt=dt,
        )

        # 4. Apply command to gimbal if simulation, delayed by latency_frames
        if self.source.kind == InputKind.SIMULATION:
            if self._latency_frames > 0:
                self._cmd_queue.append(cmd)
                delayed_cmd = self._cmd_queue.popleft()
            else:
                delayed_cmd = cmd

            if hasattr(self.source, "gimbal"):
                self.source.gimbal.command(delayed_cmd, dt)

        # 5. Build step result
        result = StepResult(
            frame=frame,
            output=output,
            command=cmd,
            truth=truth,
        )

        # Optional collector hook for Phase 8 metrics
        if self.collector is not None and hasattr(self.collector, "record"):
            self.collector.record(result)

        return result

    def run(
        self,
        frames: int | None = None,
        seconds: float | None = None,
    ) -> list[StepResult]:
        """Run the session for a specified number of frames or duration in seconds.

        Args:
            frames: Exact count of frames to process.
            seconds: Duration in seconds to process.

        Returns:
            List of StepResult instances for all executed steps.
        """
        fps = self.source.fps if getattr(self.source, "fps", 0.0) > 0.0 else self.config.camera.fps
        max_frames: int | None = None
        if frames is not None and seconds is not None:
            max_frames = min(frames, round(seconds * fps))
        elif frames is not None:
            max_frames = frames
        elif seconds is not None:
            max_frames = round(seconds * fps)

        results: list[StepResult] = []
        count = 0
        while max_frames is None or count < max_frames:
            res = self.step()
            if res is None:
                break
            results.append(res)
            count += 1

        return results


__all__ = ("Session",)
