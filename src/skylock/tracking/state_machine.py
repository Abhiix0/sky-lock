"""Deterministic tracking state machine.

Governs five operational tracking states:
- SEARCH: Sweeping with raster pattern looking for beacon candidates.
- ACQUIRE: Centering and confirming detected candidates across frames.
- TRACK: Closed-loop tracking with Kalman-filtered line-of-sight estimates.
- LOST: Coastal propagation on Kalman velocity during temporary signal loss.
- REACQUIRE: Local Archimedean spiral search around predicted LOS.

Transitions are strictly deterministic functions of detections/candidates,
time, and pointing telemetry.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from skylock.core.enums import TrackState
from skylock.core.types import StateEvent

if TYPE_CHECKING:
    from skylock.config.models import SearchConfig, TrackingConfig
    from skylock.core.types import Candidate, Detection


class StateMachine:
    """Tracking state machine with transition logging.

    No ground-truth or occlusion side channels are permitted.
    """

    def __init__(
        self,
        tracking_cfg: TrackingConfig,
        search_cfg: SearchConfig | None = None,
        min_snr: float = 3.0,
    ) -> None:
        """Initialize StateMachine.

        Args:
            tracking_cfg: Tracking and timeout parameters.
            search_cfg: Search scan parameters (defaults to tracking_cfg.search).
            min_snr: Minimum candidate SNR for acquisition gating.
        """
        self.tracking_cfg = tracking_cfg
        self.search_cfg = search_cfg if search_cfg is not None else tracking_cfg.search
        self.min_snr = float(min_snr)

        self.state: TrackState = TrackState.SEARCH
        self.state_start_time: float = 0.0
        self.last_seen_time: float = 0.0
        self.consecutive_misses: int = 0
        self._events: list[StateEvent] = []

    @property
    def events(self) -> tuple[StateEvent, ...]:
        """Immutable history of state transition events."""
        return tuple(self._events)

    @property
    def last_event(self) -> StateEvent | None:
        """Most recent state transition event, or None if no transitions."""
        return self._events[-1] if self._events else None

    def reset(self, t: float = 0.0) -> None:
        """Reset state machine to initial SEARCH state and clear event log."""
        self.state = TrackState.SEARCH
        self.state_start_time = float(t)
        self.last_seen_time = float(t)
        self.consecutive_misses = 0
        self._events.clear()

    def _transition_to(self, next_state: TrackState, t: float, reason: str) -> None:
        """Execute and record state transition."""
        if next_state == self.state:
            return

        event = StateEvent(
            timestamp_s=t,
            from_state=self.state,
            to_state=next_state,
            reason=reason,
        )
        self._events.append(event)
        self.state = next_state
        self.state_start_time = t

        if next_state == TrackState.TRACK:
            self.consecutive_misses = 0
            self.last_seen_time = t
        elif next_state == TrackState.ACQUIRE:
            self.last_seen_time = t
        elif next_state == TrackState.SEARCH:
            self.consecutive_misses = 0

    def step(
        self,
        t: float,
        candidates: Sequence[Candidate] = (),
        has_gated_measurement: bool = False,
        detections: Sequence[Detection] = (),
    ) -> TrackState:
        """Evaluate transitions based on current frame observations and elapsed time.

        Args:
            t: Current frame timestamp in seconds.
            candidates: Active candidate tracks from candidate associator.
            has_gated_measurement: Whether a gated measurement updated the Kalman filter.
            detections: Raw detections in current frame.

        Returns:
            Updated TrackState.
        """
        valid_candidates = [c for c in candidates if c.score >= self.min_snr and c.misses == 0]

        if self.state == TrackState.SEARCH:
            if valid_candidates:
                if any(c.confirmed for c in valid_candidates):
                    self._transition_to(
                        TrackState.ACQUIRE,
                        t,
                        f"Candidate detected above min SNR ({self.min_snr}) in SEARCH",
                    )
                    self._transition_to(
                        TrackState.TRACK,
                        t,
                        f"Candidate confirmed via M-of-N ({self.tracking_cfg.confirm_hits}/"
                        f"{self.tracking_cfg.confirm_window})",
                    )
                else:
                    self._transition_to(
                        TrackState.ACQUIRE,
                        t,
                        f"Candidate detected above min SNR ({self.min_snr}) in SEARCH",
                    )

        elif self.state == TrackState.ACQUIRE:
            if any(c.confirmed for c in valid_candidates):
                self._transition_to(
                    TrackState.TRACK,
                    t,
                    f"Candidate confirmed via M-of-N ({self.tracking_cfg.confirm_hits}/"
                    f"{self.tracking_cfg.confirm_window})",
                )
            elif valid_candidates:
                self.last_seen_time = t
                if (t - self.state_start_time) >= self.tracking_cfg.acquire_timeout_s:
                    self._transition_to(
                        TrackState.SEARCH,
                        t,
                        f"Acquire timeout exceeded ({self.tracking_cfg.acquire_timeout_s}s)",
                    )
            else:
                if (t - self.state_start_time) >= self.tracking_cfg.acquire_timeout_s:
                    self._transition_to(
                        TrackState.SEARCH,
                        t,
                        f"Acquire timeout exceeded ({self.tracking_cfg.acquire_timeout_s}s)",
                    )

        elif self.state == TrackState.TRACK:
            if has_gated_measurement:
                self.consecutive_misses = 0
                self.last_seen_time = t
            else:
                self.consecutive_misses += 1
                if self.consecutive_misses >= self.tracking_cfg.lost_after_misses:
                    self._transition_to(
                        TrackState.LOST,
                        t,
                        f"Consecutive misses reached limit ({self.tracking_cfg.lost_after_misses})",
                    )

        elif self.state == TrackState.LOST:
            if has_gated_measurement:
                self._transition_to(
                    TrackState.TRACK,
                    t,
                    "Gated measurement reacquired during LOST",
                )
            else:
                elapsed_coast = t - self.state_start_time
                if elapsed_coast >= self.tracking_cfg.coast_max_s:
                    self._transition_to(
                        TrackState.REACQUIRE,
                        t,
                        f"Coast duration ({elapsed_coast:.3f}s) reached coast_max_s "
                        f"({self.tracking_cfg.coast_max_s}s)",
                    )

        elif self.state == TrackState.REACQUIRE:
            has_detection = (
                any(d.snr >= self.min_snr for d in detections)
                if detections
                else bool(valid_candidates)
            )

            if has_detection or valid_candidates:
                if any(c.confirmed for c in valid_candidates):
                    self._transition_to(
                        TrackState.ACQUIRE,
                        t,
                        "Detection found in REACQUIRE",
                    )
                    self._transition_to(
                        TrackState.TRACK,
                        t,
                        f"Candidate confirmed via M-of-N ({self.tracking_cfg.confirm_hits}/"
                        f"{self.tracking_cfg.confirm_window})",
                    )
                else:
                    self._transition_to(
                        TrackState.ACQUIRE,
                        t,
                        "Detection found in REACQUIRE",
                    )
            else:
                elapsed_reacquire = t - self.state_start_time
                if elapsed_reacquire >= self.tracking_cfg.reacquire_timeout_s:
                    self._transition_to(
                        TrackState.SEARCH,
                        t,
                        f"Reacquire timeout ({elapsed_reacquire:.3f}s) exceeded "
                        f"({self.tracking_cfg.reacquire_timeout_s}s)",
                    )

        return self.state


__all__ = ("StateMachine",)
