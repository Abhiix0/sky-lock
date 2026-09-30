"""Tests for skylock.candidate_tracker — Multi-candidate tracking."""

from skylock.candidate_tracker import CandidateTracker
from skylock.config import IdConfig


class TestCandidateTracker:
    def test_instantiates_new_candidates(self):
        tracker = CandidateTracker()
        detections = [
            {"cx": 10.0, "cy": 20.0, "peak": 150.0},
            {"cx": 50.0, "cy": 60.0, "peak": 200.0},
        ]
        cands = tracker.update(detections, sim_time=1.0)

        assert len(cands) == 2
        assert cands[0]["x"] == 10.0
        assert cands[1]["x"] == 50.0
        assert len(cands[0]["history"]) == 1
        assert cands[0]["history"][0] == 150.0
        assert cands[0]["total_observations"] == 1

    def test_associates_existing_candidates(self):
        tracker = CandidateTracker(IdConfig(association_gate_px=10))

        # Frame 1
        det1 = [{"cx": 10.0, "cy": 20.0, "peak": 100.0}]
        cands1 = tracker.update(det1, sim_time=1.0)
        cand_id = cands1[0]["id"]

        # Frame 2: Move slightly
        det2 = [{"cx": 12.0, "cy": 22.0, "peak": 200.0}]
        cands2 = tracker.update(det2, sim_time=1.1)

        assert len(cands2) == 1
        assert cands2[0]["id"] == cand_id
        assert cands2[0]["x"] == 12.0
        assert cands2[0]["total_observations"] == 2
        assert len(cands2[0]["history"]) == 2
        assert cands2[0]["history"][1] == 200.0

    def test_missed_frames_incremented_and_pruned(self):
        tracker = CandidateTracker(IdConfig(max_miss_frames=2))

        # Frame 1: track 1 object
        tracker.update([{"cx": 10.0, "cy": 20.0, "peak": 100.0}], 1.0)
        assert len(tracker.candidates) == 1

        # Frame 2: empty (miss 1)
        tracker.update([], 1.1)
        assert len(tracker.candidates) == 1
        assert tracker.candidates[0]["missed_frames"] == 1
        assert tracker.candidates[0]["history"][-1] == 0.0

        # Frame 3: empty (miss 2)
        tracker.update([], 1.2)
        assert len(tracker.candidates) == 1
        assert tracker.candidates[0]["missed_frames"] == 2

        # Frame 4: empty (miss 3 - beyond limit)
        tracker.update([], 1.3)
        assert len(tracker.candidates) == 0

    def test_confirmed_candidates_survive_longer(self):
        tracker = CandidateTracker(IdConfig(max_miss_frames=2))

        tracker.update([{"cx": 10.0, "cy": 20.0, "peak": 100.0}], 1.0)
        tracker.candidates[0]["confirmed"] = True

        # Miss 3 frames
        tracker.update([], 1.1)
        tracker.update([], 1.2)
        tracker.update([], 1.3)

        # Still alive because confirmed candidates get 2x max_miss_frames (4)
        assert len(tracker.candidates) == 1

        # Miss 2 more frames (total 5)
        tracker.update([], 1.4)
        tracker.update([], 1.5)

        assert len(tracker.candidates) == 0
