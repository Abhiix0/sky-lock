"""Unit tests for the 5-state operational tracking StateMachine."""

from __future__ import annotations

import pytest

from skylock.config.models import TrackingConfig
from skylock.core.enums import TrackState
from skylock.core.types import Candidate, Detection
from skylock.tracking.state_machine import StateMachine


def _make_candidate(cand_id: int = 1, confirmed: bool = False, score: float = 10.0) -> Candidate:
    return Candidate(
        id=cand_id,
        cx=320.0,
        cy=256.0,
        age=1,
        hits=1 if not confirmed else 3,
        misses=0,
        confirmed=confirmed,
        score=score,
    )


def test_state_machine_five_state_cycle_and_logging() -> None:
    cfg = TrackingConfig(
        acquire_timeout_s=1.0,
        lost_after_misses=5,
        coast_max_s=0.5,
        reacquire_timeout_s=1.0,
    )
    sm = StateMachine(cfg, min_snr=3.0)
    assert sm.state == TrackState.SEARCH

    # 1. SEARCH -> ACQUIRE
    t = 0.1
    cand = _make_candidate(confirmed=False, score=5.0)
    state = sm.step(t, candidates=[cand])
    assert state == TrackState.ACQUIRE
    assert len(sm.events) == 1
    assert sm.events[0].from_state == TrackState.SEARCH
    assert sm.events[0].to_state == TrackState.ACQUIRE
    assert "Candidate detected" in sm.events[0].reason

    # 2. ACQUIRE -> TRACK
    t += 0.033
    cand_confirmed = _make_candidate(confirmed=True, score=6.0)
    state = sm.step(t, candidates=[cand_confirmed], has_gated_measurement=True)
    assert state == TrackState.TRACK
    assert len(sm.events) == 2
    assert sm.events[1].from_state == TrackState.ACQUIRE
    assert sm.events[1].to_state == TrackState.TRACK

    # 3. TRACK -> LOST (5 consecutive misses)
    for _ in range(4):
        t += 0.033
        state = sm.step(t, candidates=[], has_gated_measurement=False)
        assert state == TrackState.TRACK

    t += 0.033  # 5th miss
    state = sm.step(t, candidates=[], has_gated_measurement=False)
    assert state == TrackState.LOST
    assert len(sm.events) == 3
    assert sm.events[2].from_state == TrackState.TRACK
    assert sm.events[2].to_state == TrackState.LOST

    # 4. LOST -> REACQUIRE (coast_max_s = 0.5s)
    # Elapsed since entering LOST reaches 0.5s
    lost_start = sm.state_start_time
    t = lost_start + 0.49
    state = sm.step(t, candidates=[], has_gated_measurement=False)
    assert state == TrackState.LOST

    t = lost_start + 0.51
    state = sm.step(t, candidates=[], has_gated_measurement=False)
    assert state == TrackState.REACQUIRE
    assert len(sm.events) == 4
    assert sm.events[3].from_state == TrackState.LOST
    assert sm.events[3].to_state == TrackState.REACQUIRE

    # 5. REACQUIRE -> SEARCH (reacquire_timeout_s = 1.0s)
    reacquire_start = sm.state_start_time
    t = reacquire_start + 0.99
    state = sm.step(t, candidates=[], has_gated_measurement=False)
    assert state == TrackState.REACQUIRE

    t = reacquire_start + 1.01
    state = sm.step(t, candidates=[], has_gated_measurement=False)
    assert state == TrackState.SEARCH
    assert len(sm.events) == 5
    assert sm.events[4].from_state == TrackState.REACQUIRE
    assert sm.events[4].to_state == TrackState.SEARCH

    # Verify event properties
    for ev in sm.events:
        assert ev.t > 0.0
        assert len(ev.reason) > 0


def test_acquire_timeout_to_search() -> None:
    cfg = TrackingConfig(acquire_timeout_s=1.0)
    sm = StateMachine(cfg)

    # Enter ACQUIRE
    t = 0.0
    cand = _make_candidate(confirmed=False, score=5.0)
    sm.step(t, candidates=[cand])
    assert sm.state == TrackState.ACQUIRE

    # Candidate disappears; step past timeout
    dt = 0.033
    while t <= 1.05:
        t += dt
        sm.step(t, candidates=[])

    assert sm.state == TrackState.SEARCH
    assert sm.last_event is not None
    assert sm.last_event.to_state == TrackState.SEARCH
    assert "timeout" in sm.last_event.reason.lower()


def test_lost_recovery_to_track() -> None:
    cfg = TrackingConfig(lost_after_misses=2)
    sm = StateMachine(cfg)

    # Go to TRACK
    cand = _make_candidate(confirmed=True)
    sm.step(0.0, candidates=[cand])
    assert sm.state == TrackState.TRACK

    # Miss 2 frames -> LOST
    sm.step(0.033, has_gated_measurement=False)
    sm.step(0.066, has_gated_measurement=False)
    assert sm.state == TrackState.LOST

    # Gated measurement received during LOST -> recovery to TRACK
    sm.step(0.100, has_gated_measurement=True)
    assert sm.state == TrackState.TRACK
    assert sm.last_event is not None
    assert sm.last_event.from_state == TrackState.LOST
    assert sm.last_event.to_state == TrackState.TRACK


def test_reacquire_timeout_timing() -> None:
    """REACQUIRE->SEARCH at reacquire_timeout_s +/- one frame period (33 ms)."""
    frame_period = 0.033
    cfg = TrackingConfig(reacquire_timeout_s=1.0, coast_max_s=0.2, lost_after_misses=1)
    sm = StateMachine(cfg)

    # Force to REACQUIRE
    cand = _make_candidate(confirmed=True)
    sm.step(0.0, candidates=[cand])
    sm.step(0.033, has_gated_measurement=False)  # LOST
    sm.step(0.25, has_gated_measurement=False)   # REACQUIRE

    assert sm.state == TrackState.REACQUIRE
    reacquire_start = sm.state_start_time

    # Step at 33ms frames until transition
    t = reacquire_start
    while sm.state == TrackState.REACQUIRE:
        t += frame_period
        sm.step(t, candidates=[], has_gated_measurement=False)

    elapsed_in_reacquire = t - reacquire_start
    assert sm.state == TrackState.SEARCH
    assert elapsed_in_reacquire == pytest.approx(1.0, abs=frame_period + 1e-4)


def test_reacquire_detection_leads_to_acquire_and_track() -> None:
    cfg = TrackingConfig(reacquire_timeout_s=2.0, coast_max_s=0.2, lost_after_misses=1)
    sm = StateMachine(cfg)
    cand = _make_candidate(confirmed=True)
    sm.step(0.0, candidates=[cand])
    sm.step(0.033, has_gated_measurement=False)  # LOST
    sm.step(0.300, has_gated_measurement=False)  # REACQUIRE
    assert sm.state == TrackState.REACQUIRE

    # Detection in REACQUIRE
    det = Detection(cx=320.0, cy=256.0, area_px=20.0, peak=200.0, snr=10.0, bbox=(310, 246, 20, 20))
    sm.step(0.400, detections=[det])
    assert sm.state in (TrackState.ACQUIRE, TrackState.TRACK)
