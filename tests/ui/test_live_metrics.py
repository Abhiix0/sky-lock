"""Unit tests for the pure-python LiveMetrics tracker."""

from __future__ import annotations

import pytest

from skylock.core.enums import TrackState
from skylock.ui.live_metrics import LiveMetrics


def test_initial_state_and_none_before_track() -> None:
    """Verify metrics initial state has lock_retention=None before first TRACK."""
    lm = LiveMetrics()
    snap = lm.snapshot()

    assert snap["frames"] == 0
    assert snap["lock_retention"] is None
    assert snap["loss_events"] == 0
    assert snap["last_reacq_s"] is None
    assert snap["current_loss_s"] is None
    assert snap["err_mean"] is None
    assert snap["err_rms"] is None
    assert snap["err_max"] is None
    assert snap["detections_total"] == 0
    assert snap["state_frames"][TrackState.SEARCH.name] == 0

    # Advance through SEARCH and ACQUIRE without reaching TRACK
    lm.update(TrackState.SEARCH, timestamp_s=0.1, n_detections=0, tracking_error_px=None)
    lm.update(TrackState.ACQUIRE, timestamp_s=0.2, n_detections=1, tracking_error_px=None)

    snap = lm.snapshot()
    assert snap["frames"] == 2
    assert snap["detections_total"] == 1
    assert snap["lock_retention"] is None
    assert snap["loss_events"] == 0
    assert snap["state_frames"][TrackState.SEARCH.name] == 1
    assert snap["state_frames"][TrackState.ACQUIRE.name] == 1


def test_scripted_state_sequence_lock_retention_and_loss() -> None:
    """Scripted state transitions to verify exact lock retention, loss events, and reacq time.

    Sequence:
    Frame 1: SEARCH (t=0.0) -> before TRACK
    Frame 2: TRACK (t=0.1)  -> post-first-track frame 1 (in TRACK)
    Frame 3: TRACK (t=0.2)  -> post-first-track frame 2 (in TRACK)
    Frame 4: LOST (t=0.3)   -> post-first-track frame 3 (loss event 1 begins at t=0.3)
    Frame 5: REACQUIRE (t=0.4) -> post-first-track frame 4 (still in loss)
    Frame 6: TRACK (t=0.6)  -> post-first-track frame 5 (loss ends, reacq = 0.6 - 0.3 = 0.3s)
    """
    lm = LiveMetrics()

    lm.update(TrackState.SEARCH, 0.0, 0, None)
    assert lm.snapshot()["lock_retention"] is None

    lm.update(TrackState.TRACK, 0.1, 1, 2.0)
    snap = lm.snapshot()
    assert snap["lock_retention"] == 1.0  # 1/1
    assert snap["loss_events"] == 0
    assert snap["last_reacq_s"] is None

    lm.update(TrackState.TRACK, 0.2, 1, 4.0)
    snap = lm.snapshot()
    assert snap["lock_retention"] == 1.0  # 2/2

    lm.update(TrackState.LOST, 0.3, 0, None)
    snap = lm.snapshot()
    assert snap["lock_retention"] == pytest.approx(2.0 / 3.0)
    assert snap["loss_events"] == 1
    assert snap["current_loss_s"] == pytest.approx(0.0)
    assert snap["last_reacq_s"] is None

    lm.update(TrackState.REACQUIRE, 0.4, 1, None)
    snap = lm.snapshot()
    assert snap["lock_retention"] == pytest.approx(2.0 / 4.0)
    assert snap["loss_events"] == 1
    assert snap["current_loss_s"] == pytest.approx(0.1)

    lm.update(TrackState.TRACK, 0.6, 1, 6.0)
    snap = lm.snapshot()
    assert snap["lock_retention"] == pytest.approx(3.0 / 5.0)
    assert snap["loss_events"] == 1
    assert snap["current_loss_s"] is None
    assert snap["last_reacq_s"] == pytest.approx(0.3)  # 0.6 - 0.3

    # Check tracking error aggregates: errors were 2.0, 4.0, 6.0
    # Mean = 4.0, RMS = sqrt((4 + 16 + 36)/3) = sqrt(56/3) ~ 4.32049, Max = 6.0
    assert snap["err_mean"] == pytest.approx(4.0)
    assert snap["err_rms"] == pytest.approx((56.0 / 3.0) ** 0.5)
    assert snap["err_max"] == pytest.approx(6.0)


def test_reset_clears_all_metrics() -> None:
    """Verify calling reset() restores pristine initial conditions."""
    lm = LiveMetrics()
    lm.update(TrackState.TRACK, 1.0, 2, 5.0)
    assert lm.snapshot()["frames"] == 1
    assert lm.snapshot()["lock_retention"] == 1.0

    lm.reset()
    snap = lm.snapshot()
    assert snap["frames"] == 0
    assert snap["lock_retention"] is None
    assert snap["loss_events"] == 0
    assert snap["err_mean"] is None
    assert snap["detections_total"] == 0
