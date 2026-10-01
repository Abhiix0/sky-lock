"""Negative-case validation tests.

1. Target beyond reach: acquisition must result in NOT_ACQUIRED verdict and
   overall verdict must not be PASS.
2. Permanent disappearance: after target disappears, REACQUIRE→SEARCH fires
   at reacquire_timeout_s ± one frame period.
"""

from __future__ import annotations

from skylock.app.session import Session
from skylock.config.io import override
from skylock.config.presets import spec_default
from skylock.core.enums import MetricStatus, TrackState, Verdict
from skylock.metrics.collector import MetricsCollector
from skylock.metrics.requirements import evaluate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FRAME_PERIOD_S = 1.0 / 30.0  # 30 Hz → 1 frame ≈ 33.3 ms


def _build_unreachable_cfg():
    """Target placed 20° from boresight — physically unreachable within acquisition_max_s=2 s."""
    base_cfg = spec_default()
    return override(
        base_cfg,
        {
            "seed": 1,
            "target.count": 1,
            "target.targets": [
                {
                    "id": "target_far",
                    "size_px": 10,
                    "shape": "disc",
                    "brightness": 220.0,
                    "initial": "fixed",
                    "initial_pos_deg": [20.0, 15.0],  # Well outside gimbal reach
                    "motion": {"kind": "line", "speed_deg_s": 0.0, "heading_deg": 0.0},
                }
            ],
        },
    )


def _build_disappear_cfg():
    """Target starts in FOV, then permanently disappears via a visibility window."""
    base_cfg = spec_default()
    # target visible 0..2 s only, then gone forever
    return override(
        base_cfg,
        {
            "seed": 2,
            "target.count": 1,
            "target.targets": [
                {
                    "id": "target_vanish",
                    "size_px": 10,
                    "shape": "disc",
                    "brightness": 220.0,
                    "initial": "fixed",
                    "initial_pos_deg": [2.0, 1.0],
                    "motion": {"kind": "line", "speed_deg_s": 0.3, "heading_deg": 0.0},
                    # visibility_windows are OCCLUSION windows: target hidden while inside.
                    # Occlude from 2.5 s onward — permanently gone after TRACK is reached.
                    "visibility_windows": [[2.5, 9999.0]],
                }
            ],
            # Ensure reacquire_timeout_s is the spec default 1.0 s
            "tracking.reacquire_timeout_s": 1.0,
            "tracking.coast_max_s": 0.5,
        },
    )


# ---------------------------------------------------------------------------
# Test 1: Unreachable target → NOT_ACQUIRED
# ---------------------------------------------------------------------------

def test_unreachable_target_not_acquired() -> None:
    """Target 20° away must not be acquired within the acquisition window."""
    cfg = _build_unreachable_cfg()

    collector = MetricsCollector(cfg)
    session = Session(cfg, collector=collector)
    session.source.open()

    # Run long enough that the acquisition window certainly passes (5 s >> 2 s)
    session.run(seconds=5.0)

    run_metrics = collector.finalize()
    verdicts = evaluate(run_metrics, cfg.requirements)

    # The acquisition-from-observable metric must be NOT_ACQUIRED (never reached TRACK)
    acq = run_metrics.acquisition_time_from_observable_s
    acq_start = run_metrics.acquisition_time_from_start_s  # noqa: F841 (captured for debugging)
    assert acq.status in (MetricStatus.NOT_ACQUIRED, MetricStatus.NOT_RUN), (
        f"Expected NOT_ACQUIRED or NOT_RUN for unreachable target, got {acq.status} "
        f"(value={acq.value})"
    )
    # successful_acquisition must not be True
    if run_metrics.successful_acquisition.status == MetricStatus.MEASURED:
        assert run_metrics.successful_acquisition.value is False, (
            "Unreachable target must not record successful_acquisition=True"
        )

    # Overall verdict must not be PASS
    assert verdicts.get("overall") != Verdict.PASS, (
        f"Overall verdict should not be PASS for an unreachable target, got {verdicts}"
    )

    # Acquisition verdict must be FAIL or INDETERMINATE (not PASS)
    assert verdicts.get("acquisition_time") != Verdict.PASS, (
        f"acquisition_time verdict should not be PASS, got {verdicts}"
    )


def test_unreachable_target_session_runs_without_crash() -> None:
    """Session must complete without exception even when target is unreachable."""
    cfg = _build_unreachable_cfg()
    session = Session(cfg)
    session.source.open()

    results = session.run(seconds=5.0)
    assert results, "Session produced no results for unreachable target"

    # All frames must be in SEARCH or at most ACQUIRE (never TRACK)
    states_seen = {r.output.state for r in results}
    assert TrackState.TRACK not in states_seen, (
        f"Unreachable target somehow reached TRACK. States seen: {states_seen}"
    )


# ---------------------------------------------------------------------------
# Test 2: Permanent disappearance → REACQUIRE → SEARCH at deadline
# ---------------------------------------------------------------------------

def test_permanent_disappearance_reacquire_to_search() -> None:
    """After target disappears permanently, REACQUIRE→SEARCH must fire at deadline."""
    cfg = _build_disappear_cfg()
    reacquire_timeout_s: float = cfg.tracking.reacquire_timeout_s  # 1.0 s
    coast_max_s: float = cfg.tracking.coast_max_s  # 0.5 s

    collector = MetricsCollector(cfg)
    session = Session(cfg, collector=collector)
    session.source.open()

    # Run long enough for TRACK→LOST→REACQUIRE→SEARCH to complete
    # Need: ~2.5 s to reach TRACK, then coast_max_s, then reacquire_timeout_s
    run_s = 2.5 + coast_max_s + reacquire_timeout_s + 2.0
    session.run(seconds=run_s)

    events = session.pipeline.events
    transitions = [(e.from_state, e.to_state, e.timestamp_s) for e in events]

    # Must have transitioned REACQUIRE → SEARCH
    reacq_to_search = [
        (frm, to, t)
        for frm, to, t in transitions
        if frm == TrackState.REACQUIRE and to == TrackState.SEARCH
    ]

    assert reacq_to_search, (
        f"Expected REACQUIRE→SEARCH transition but events were: {transitions}"
    )

    # Find the REACQUIRE entry time and check the timeout fires within ±1 frame
    reacquire_entries = [
        (frm, to, t)
        for frm, to, t in transitions
        if to == TrackState.REACQUIRE
    ]
    if reacquire_entries:
        _, _, t_reacquire_entry = reacquire_entries[-1]
        _, _, t_search_return = reacq_to_search[-1]
        actual_reacquire_duration = t_search_return - t_reacquire_entry

        assert abs(actual_reacquire_duration - reacquire_timeout_s) <= _FRAME_PERIOD_S + 1e-6, (
            f"REACQUIRE→SEARCH fired after {actual_reacquire_duration:.4f} s, "
            f"expected {reacquire_timeout_s:.4f} s ± {_FRAME_PERIOD_S:.4f} s (1 frame)"
        )


def test_permanent_disappearance_final_state_search() -> None:
    """After the target disappears permanently the session should end in SEARCH."""
    cfg = _build_disappear_cfg()
    reacquire_timeout_s: float = cfg.tracking.reacquire_timeout_s
    coast_max_s: float = cfg.tracking.coast_max_s

    session = Session(cfg)
    session.source.open()

    run_s = 2.5 + coast_max_s + reacquire_timeout_s + 2.5
    results = session.run(seconds=run_s)

    assert results, "No results produced"
    final_state = results[-1].output.state
    assert final_state == TrackState.SEARCH, (
        f"Expected final state SEARCH after permanent disappearance, got {final_state}"
    )
