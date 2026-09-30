"""Multi-candidate track association and temporal M-of-N confirmation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from skylock.config.models import TrackingConfig
from skylock.core.types import Candidate, Detection


@dataclass(slots=True)
class _CandidateRecord:
    """Internal mutable tracking state for an active candidate."""

    id: int
    cx: float
    cy: float
    age: int
    hits: int
    misses: int
    history: list[int]
    confirmed: bool
    score: float


class CandidateTracker:
    """Multi-candidate nearest-neighbour association with M-of-N confirmation.

    Maintains candidate continuity across frames, suppresses transient false alarms,
    and assigns monotonic track IDs.
    """

    def __init__(self, config: TrackingConfig) -> None:
        self.config = config
        self._candidates: list[_CandidateRecord] = []
        self._next_id: int = 1

    def reset(self) -> None:
        """Reset internal candidate tracks and restore initial monotonic ID counter."""
        self._candidates.clear()
        self._next_id = 1

    def update(
        self,
        detections: list[Detection],
        frame_index: int,
        predicted_px: tuple[float, float] | None = None,
    ) -> list[Candidate]:
        """Associate detections with active candidates and update track states.

        Args:
            detections: Candidate blob detections in the current frame.
            frame_index: Current frame index.
            predicted_px: Optional Kalman filter predicted position for the primary target.

        Returns:
            List of active immutable Candidate instances.
        """
        matched_cand_indices: set[int] = set()
        matched_det_indices: set[int] = set()

        # 1. Compute candidate-detection association distance pairs within adaptive gate
        pairs: list[tuple[float, int, int]] = []
        for c_idx, cand in enumerate(self._candidates):
            # Use predicted position for primary confirmed candidate if available
            if cand.confirmed and predicted_px is not None and c_idx == 0:
                ref_x, ref_y = predicted_px
            else:
                ref_x, ref_y = cand.cx, cand.cy

            # Gate expands per consecutive miss to handle target acceleration
            gate = self.config.association_gate_px + float(cand.misses) * 5.0

            for d_idx, det in enumerate(detections):
                dist = math.hypot(ref_x - det.cx, ref_y - det.cy)
                if dist <= gate:
                    pairs.append((dist, c_idx, d_idx))

        # 2. Greedy nearest-neighbour one-to-one matching
        pairs.sort(key=lambda p: p[0])
        for _dist, c_idx, d_idx in pairs:
            if c_idx not in matched_cand_indices and d_idx not in matched_det_indices:
                matched_cand_indices.add(c_idx)
                matched_det_indices.add(d_idx)

                cand = self._candidates[c_idx]
                det = detections[d_idx]
                cand.cx = det.cx
                cand.cy = det.cy
                cand.age += 1
                cand.hits += 1
                cand.misses = 0
                cand.history.append(1)
                if len(cand.history) > self.config.confirm_window:
                    cand.history.pop(0)

                # M-of-N confirmation check
                if sum(cand.history) >= self.config.confirm_hits:
                    cand.confirmed = True
                cand.score = det.snr

        # 3. Handle unmatched active candidates (missed observation)
        for c_idx, cand in enumerate(self._candidates):
            if c_idx not in matched_cand_indices:
                cand.age += 1
                cand.misses += 1
                cand.history.append(0)
                if len(cand.history) > self.config.confirm_window:
                    cand.history.pop(0)

                if not cand.confirmed and sum(cand.history) >= self.config.confirm_hits:
                    cand.confirmed = True

        # 4. Prune lost candidates exceeding lost_after_misses
        self._candidates = [
            c for c in self._candidates if c.misses < self.config.lost_after_misses
        ]

        # 5. Instantiate new track candidates for unassociated detections
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_det_indices:
                is_initially_confirmed = self.config.confirm_hits <= 1
                new_cand = _CandidateRecord(
                    id=self._next_id,
                    cx=det.cx,
                    cy=det.cy,
                    age=1,
                    hits=1,
                    misses=0,
                    history=[1],
                    confirmed=is_initially_confirmed,
                    score=det.snr,
                )
                self._next_id += 1
                self._candidates.append(new_cand)

        # 6. Return immutable Candidate models
        return [
            Candidate(
                id=c.id,
                cx=c.cx,
                cy=c.cy,
                age=c.age,
                hits=c.hits,
                misses=c.misses,
                confirmed=c.confirmed,
                score=c.score,
            )
            for c in self._candidates
        ]
