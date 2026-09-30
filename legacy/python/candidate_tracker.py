"""
Multi-Candidate Tracker with Nearest-Neighbor Data Association.

Maintains rolling intensity history per candidate for matched-filter
blink code correlation.

JS reference: src/tracking/candidateTracker.js
"""

from __future__ import annotations

import math
from typing import Any

from skylock.config import ID_CONFIG, IdConfig


class CandidateTracker:
    """Tracks multiple blob candidates across frames using nearest-neighbor."""

    def __init__(self, config: IdConfig = ID_CONFIG) -> None:
        self._cfg = config

        self.candidates: list[dict[str, Any]] = []
        self._next_candidate_id: int = 1

    def update(
        self,
        detections: list[dict[str, Any]],
        sim_time: float = 0.0,
        predicted_pos: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """Update candidates with detections from the current frame.

        Args:
            detections: List of detected blobs.
            sim_time: Simulation time in seconds.
            predicted_pos: Optional Kalman predicted pixel {x, y}.

        Returns:
            Updated candidates list.
        """
        matched_det_indices = set()
        matched_cand_ids = set()

        max_history = self._cfg.history_window_frames
        association_gate = self._cfg.association_gate_px
        max_miss_frames = self._cfg.max_miss_frames

        # 1. Data Association (Nearest-Neighbor)
        for candidate in self.candidates:
            best_dist = float("inf")
            best_det_idx = -1

            # Expand gate if candidate has missed frames
            if candidate.get("confirmed") and predicted_pos:
                gate = association_gate * 1.5
            else:
                gate = association_gate + candidate.get("missed_frames", 0) * 2.0

            for i, d in enumerate(detections):
                if i in matched_det_indices:
                    continue
                dist = math.hypot(d["cx"] - candidate["x"], d["cy"] - candidate["y"])

                if dist <= gate and dist < best_dist:
                    best_dist = dist
                    best_det_idx = i

            if best_det_idx != -1:
                # Associated
                d = detections[best_det_idx]
                candidate["x"] = d["cx"]
                candidate["y"] = d["cy"]
                candidate["last_detection"] = d
                candidate["missed_frames"] = 0
                candidate["total_observations"] = candidate.get("total_observations", 0) + 1
                candidate["last_seen_time"] = sim_time

                intensity = float(d["peak"]) if d["peak"] > 0 else 1.0
                candidate["history"].append(intensity)
                if len(candidate["history"]) > max_history:
                    candidate["history"].pop(0)

                matched_det_indices.add(best_det_idx)
                matched_cand_ids.add(candidate["id"])
            else:
                # Missed
                candidate["missed_frames"] = candidate.get("missed_frames", 0) + 1
                candidate["history"].append(0.0)
                if len(candidate["history"]) > max_history:
                    candidate["history"].pop(0)

        # 2. Instantiate new candidates
        for i, d in enumerate(detections):
            if i in matched_det_indices:
                continue

            intensity = float(d["peak"]) if d["peak"] > 0 else 1.0
            new_cand = {
                "id": self._next_candidate_id,
                "x": d["cx"],
                "y": d["cy"],
                "last_detection": d,
                "missed_frames": 0,
                "total_observations": 1,
                "last_seen_time": sim_time,
                "history": [intensity],
                "score": 0.0,
                "confirmed": False,
                "confirm_streak": 0,
            }
            self._next_candidate_id += 1
            self.candidates.append(new_cand)

        # 3. Prune dead candidates
        surviving = []
        for c in self.candidates:
            allowed_misses = max_miss_frames * 2 if c.get("confirmed") else max_miss_frames
            if c.get("missed_frames", 0) <= allowed_misses:
                surviving.append(c)

        self.candidates = surviving
        return self.candidates

    def reset(self) -> None:
        """Reset candidate tracker."""
        self.candidates = []
        self._next_candidate_id = 1
