"""Tracking pipeline connecting blob detection, candidate association, and Kalman tracking."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from skylock.core.types import PipelineOutput
from skylock.tracking.tracker import Tracker
from skylock.vision.detector import ClassicalBlobDetector

if TYPE_CHECKING:
    from skylock.config.models import SkyLockConfig
    from skylock.core.interfaces import Detector
    from skylock.core.types import Frame, StateEvent


class TrackingPipeline:
    """Image-only tracking pipeline processing individual video frames.

    Orchestrates:
    - Adaptive ROI gating
    - Blob detection via Detector protocol
    - Multi-candidate association and confirmation
    - Kalman state filtering
    - Operational state transitions
    - ControlIntent generation
    """

    def __init__(
        self,
        config: SkyLockConfig,
        detector: Detector | None = None,
    ) -> None:
        """Initialize TrackingPipeline.

        Args:
            config: Authoritative configuration.
            detector: Optional injectable blob detector conforming to Detector protocol.
        """
        self.config = config
        self.detector: Detector = (
            detector if detector is not None else ClassicalBlobDetector(config.detection)
        )
        self.tracker: Tracker = Tracker(config)

    @property
    def events(self) -> tuple[StateEvent, ...]:
        """Sequence of state transition events emitted by state machine."""
        return self.tracker.state_machine.events

    def reset(self, t: float = 0.0) -> None:
        """Reset internal detector, candidates, Kalman filter, and state machine."""
        self.detector.reset()
        self.tracker.reset(t)

    def process(self, frame: Frame) -> PipelineOutput:
        """Execute one complete vision-tracking cycle on an input sensor frame.

        Measures processing latency around detector and tracker execution using perf_counter.

        Args:
            frame: 2-D monochrome video frame with optional pointing telemetry.

        Returns:
            PipelineOutput containing detections, candidate, target estimate, and control intent.
        """
        t0 = time.perf_counter()

        # Dynamic ROI calculation around Kalman predicted target position
        h, w = frame.image.shape
        roi = self.tracker.get_roi(width=w, height=h)

        # Blob detection
        detections = self.detector.detect(frame, roi=roi)

        # Tracker step
        state, estimate, selected_candidate, intent = self.tracker.step(frame, detections)

        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0

        return PipelineOutput(
            frame_index=frame.index,
            timestamp_s=frame.timestamp_s,
            state=state,
            estimate=estimate,
            detections=tuple(detections),
            selected=selected_candidate,
            intent=intent,
            latency_ms=latency_ms,
        )


__all__ = ("TrackingPipeline",)
