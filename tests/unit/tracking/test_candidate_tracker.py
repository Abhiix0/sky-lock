"""Unit tests for CandidateTracker association, confirmation, and drop logic."""

from skylock.config.models import TrackingConfig
from skylock.core.types import Detection
from skylock.tracking.candidate_tracker import CandidateTracker


def _make_det(cx: float, cy: float, snr: float = 20.0) -> Detection:
    return Detection(
        cx=cx,
        cy=cy,
        area_px=100.0,
        peak=220.0,
        snr=snr,
        bbox=(int(cx - 5), int(cy - 5), 10, 10),
    )


def test_association_id_stability_moving_blob() -> None:
    """A target moving at 15 px/frame preserves its candidate ID across frames."""
    cfg = TrackingConfig(association_gate_px=30.0)
    tracker = CandidateTracker(cfg)

    cand_ids: list[int] = []
    curr_x, curr_y = 100.0, 100.0

    for f in range(10):
        det = _make_det(curr_x, curr_y)
        candidates = tracker.update([det], frame_index=f)

        assert len(candidates) == 1
        cand_ids.append(candidates[0].id)

        # Move 15 px along X
        curr_x += 15.0

    # All candidate IDs must be identical
    assert len(set(cand_ids)) == 1, f"Candidate ID changed during tracking: {cand_ids}"


def test_confirmation_after_three_hits() -> None:
    """Candidate confirms after exactly 3 hits (confirm_hits = 3)."""
    cfg = TrackingConfig(confirm_hits=3, confirm_window=5)
    tracker = CandidateTracker(cfg)

    # Frame 0: 1st hit -> unconfirmed
    c0 = tracker.update([_make_det(100.0, 100.0)], frame_index=0)
    assert len(c0) == 1
    assert c0[0].confirmed is False
    assert c0[0].hits == 1

    # Frame 1: 2nd hit -> unconfirmed
    c1 = tracker.update([_make_det(102.0, 100.0)], frame_index=1)
    assert len(c1) == 1
    assert c1[0].confirmed is False
    assert c1[0].hits == 2

    # Frame 2: 3rd hit -> CONFIRMED
    c2 = tracker.update([_make_det(104.0, 100.0)], frame_index=2)
    assert len(c2) == 1
    assert c2[0].confirmed is True
    assert c2[0].hits == 3


def test_miss_handling_and_pruning() -> None:
    """Candidate survives up to lost_after_misses - 1 and is dropped on reaching limit."""
    cfg = TrackingConfig(confirm_hits=1, lost_after_misses=3)
    tracker = CandidateTracker(cfg)

    # Acquire candidate
    tracker.update([_make_det(100.0, 100.0)], frame_index=0)

    # Miss 1 (Frame 1)
    c1 = tracker.update([], frame_index=1)
    assert len(c1) == 1
    assert c1[0].misses == 1

    # Miss 2 (Frame 2)
    c2 = tracker.update([], frame_index=2)
    assert len(c2) == 1
    assert c2[0].misses == 2

    # Miss 3 (Frame 3) -> Reached lost_after_misses (3) -> Pruned!
    c3 = tracker.update([], frame_index=3)
    assert len(c3) == 0, f"Candidate was not pruned on reaching limit: {c3}"


def test_tracker_reset() -> None:
    """Reset clears candidates and restarts monotonic IDs from 1."""
    cfg = TrackingConfig()
    tracker = CandidateTracker(cfg)

    tracker.update([_make_det(50.0, 50.0)], frame_index=0)
    tracker.update([_make_det(200.0, 200.0)], frame_index=1)

    tracker.reset()
    c = tracker.update([_make_det(100.0, 100.0)], frame_index=0)
    assert len(c) == 1
    assert c[0].id == 1, f"Expected restarted ID 1, got {c[0].id}"


def test_two_blobs_separated_do_not_swap_ids() -> None:
    """Two targets moving in parallel maintain their separate IDs without swapping."""
    cfg = TrackingConfig(association_gate_px=25.0)
    tracker = CandidateTracker(cfg)

    # Initial frame: target 1 at y=100, target 2 at y=200 (separated by 100 px >> gate 25)
    dets_0 = [_make_det(50.0, 100.0), _make_det(50.0, 200.0)]
    cands_0 = tracker.update(dets_0, frame_index=0)
    assert len(cands_0) == 2
    id_top = next(c.id for c in cands_0 if abs(c.cy - 100.0) < 5)
    id_bot = next(c.id for c in cands_0 if abs(c.cy - 200.0) < 5)
    assert id_top != id_bot

    # Advance both by 10 px
    dets_1 = [_make_det(60.0, 100.0), _make_det(60.0, 200.0)]
    cands_1 = tracker.update(dets_1, frame_index=1)
    assert len(cands_1) == 2

    new_id_top = next(c.id for c in cands_1 if abs(c.cy - 100.0) < 5)
    new_id_bot = next(c.id for c in cands_1 if abs(c.cy - 200.0) < 5)

    assert new_id_top == id_top
    assert new_id_bot == id_bot
