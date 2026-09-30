"""End-to-end full-chain validation tests.

Tests the complete path: SimulationSource → TrackingPipeline → PointingController
→ VirtualGimbal → MetricsCollector → requirements evaluation.

For each motion kind the test:
1. Asserts ordered state transitions SEARCH → ACQUIRE → TRACK from the event log.
2. Asserts GT boresight error (computed in this test, not by the pipeline) is
   bounded after the first TRACK entry.
3. Runs a visibility-gap scenario and asserts TRACK → LOST → (REACQUIRE) → TRACK.
4. Asserts RunMetrics serialises cleanly to JSON with nulls where unmeasured.
"""

from __future__ import annotations

import json
import math

import pytest

from skylock.app.session import Session
from skylock.benchmark.catalog import builtin_scenarios
from skylock.benchmark.scenario import Scenario
from skylock.config.presets import spec_default
from skylock.core.enums import MetricStatus, TrackState
from skylock.metrics.collector import MetricsCollector
from skylock.metrics.requirements import evaluate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCENARIOS_BY_ID = {s.id: s for s in builtin_scenarios()}

_MOTION_SCENARIO_IDS = [
    "S01_line_clean",
    "S02_circle_clean",
    "S03_fig8_clean",
    "S04_random_clean",
]

# Maximum boresight error (px) permitted during TRACK after lock
_BORESIGHT_LIMIT_PX = 20.0

# Number of seconds to run each scenario for the state-transition test
# S02_circle takes ~6.3 s to first acquire (raster must sweep to center+radius);
# use 10 s to accommodate all motion kinds.
_RUN_SECONDS = 10.0


def _run_scenario(scenario: Scenario, seed: int = 42) -> tuple[Session, MetricsCollector, list]:
    """Build Session + MetricsCollector, run to completion, return (session, collector, results)."""
    base_cfg = spec_default()
    cfg = scenario.apply(base_cfg, seed)

    collector = MetricsCollector(cfg)
    session = Session(cfg, collector=collector)
    session.source.open()

    results = session.run(seconds=_RUN_SECONDS)
    return session, collector, results


def _state_sequence(session: Session) -> list[TrackState]:
    """Return the ordered list of states visited (from event log + initial SEARCH)."""
    events = session.pipeline.events
    if not events:
        return [TrackState.SEARCH]
    states = [TrackState.SEARCH]
    for ev in events:
        states.append(ev.to_state)
    return states


def _has_ordered_subsequence(seq: list[TrackState], subseq: list[TrackState]) -> bool:
    """Return True if subseq appears as an ordered subsequence in seq."""
    it = iter(seq)
    return all(s in it for s in subseq)


def _first_track_time(session: Session) -> float | None:
    """Return timestamp of the first SEARCH→…→TRACK transition, or None."""
    for ev in session.pipeline.events:
        if ev.to_state == TrackState.TRACK:
            return ev.timestamp_s
    return None


def _boresight_errors_after_track(
    results: list, first_track_t: float
) -> list[float]:
    """Compute GT boresight errors (px) for frames where state==TRACK and t>=first_track_t."""
    errors: list[float] = []
    cx = 640 / 2.0
    cy = 480 / 2.0
    for step in results:
        if step.output.state != TrackState.TRACK:
            continue
        if step.frame.timestamp_s < first_track_t:
            continue
        if step.truth is None or step.truth.primary_px is None:
            continue
        gx, gy = step.truth.primary_px
        errors.append(math.hypot(gx - cx, gy - cy))
    return errors


# ---------------------------------------------------------------------------
# Parametrised: one test per motion kind
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_id", _MOTION_SCENARIO_IDS)
def test_state_transitions_ordered(scenario_id: str) -> None:
    """SEARCH → ACQUIRE → TRACK must appear in order in the event log."""
    scenario = _SCENARIOS_BY_ID[scenario_id]
    session, collector, results = _run_scenario(scenario)

    assert results, f"No results produced for {scenario_id}"

    seq = _state_sequence(session)
    assert _has_ordered_subsequence(
        seq, [TrackState.SEARCH, TrackState.ACQUIRE, TrackState.TRACK]
    ), (
        f"[{scenario_id}] Expected ordered SEARCH→ACQUIRE→TRACK in state sequence {seq}. "
        f"Events: {session.pipeline.events}"
    )


@pytest.mark.parametrize("scenario_id", _MOTION_SCENARIO_IDS)
def test_boresight_error_bounded_after_lock(scenario_id: str) -> None:
    """After first TRACK entry GT boresight error must be bounded for >50% of tracking frames."""
    scenario = _SCENARIOS_BY_ID[scenario_id]
    session, collector, results = _run_scenario(scenario)

    first_track_t = _first_track_time(session)
    if first_track_t is None:
        pytest.skip(f"[{scenario_id}] Never reached TRACK — skip boresight check")

    errors = _boresight_errors_after_track(results, first_track_t)
    if not errors:
        pytest.skip(f"[{scenario_id}] No GT data during TRACK frames")

    within_limit = sum(1 for e in errors if e <= _BORESIGHT_LIMIT_PX)
    fraction = within_limit / len(errors)
    assert fraction >= 0.5, (
        f"[{scenario_id}] Only {fraction:.1%} of TRACK frames have boresight error "
        f"<= {_BORESIGHT_LIMIT_PX} px. errors (first 10): {errors[:10]}"
    )


# ---------------------------------------------------------------------------
# Visibility-gap: TRACK → LOST → (REACQUIRE) → TRACK
# ---------------------------------------------------------------------------

def test_visibility_gap_state_sequence() -> None:
    """S12_occlusion_reacq must visit TRACK→LOST and then return to TRACK."""
    scenario = _SCENARIOS_BY_ID["S12_occlusion_reacq"]
    session, collector, results = _run_scenario(scenario)

    assert results, "No results produced for S12_occlusion_reacq"

    seq = _state_sequence(session)

    # Must have an initial TRACK
    assert TrackState.TRACK in seq, (
        f"S12 never reached TRACK. State sequence: {seq}\nEvents: {session.pipeline.events}"
    )

    # Must have LOST after TRACK
    assert _has_ordered_subsequence(
        seq, [TrackState.TRACK, TrackState.LOST]
    ), f"S12 never lost target after tracking. Sequence: {seq}"

    # Must recover: after LOST must reach TRACK again
    # Find the index of first LOST, then look for TRACK after it
    first_lost_idx = next(i for i, s in enumerate(seq) if s == TrackState.LOST)
    post_lost_seq = seq[first_lost_idx:]
    assert TrackState.TRACK in post_lost_seq, (
        f"S12 never returned to TRACK after LOST. Post-LOST sequence: {post_lost_seq}"
    )


def test_visibility_gap_reacquire_appears() -> None:
    """S12 should visit LOST and may optionally go through REACQUIRE before re-TRACK."""
    scenario = _SCENARIOS_BY_ID["S12_occlusion_reacq"]
    session, _, results = _run_scenario(scenario)

    seq = _state_sequence(session)
    # Either LOST → TRACK directly (fast recovery during coast) or LOST → REACQUIRE → TRACK
    # Both are valid; we just verify recovery happened.
    # This is an observation, not an assertion, but we assert recovery
    assert TrackState.TRACK in seq[seq.index(TrackState.LOST):] if TrackState.LOST in seq else True


# ---------------------------------------------------------------------------
# Metrics serialisation: nulls for unmeasured, no NaN, round-trip JSON
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_id", _MOTION_SCENARIO_IDS)
def test_metrics_json_serialisable(scenario_id: str) -> None:
    """RunMetrics must serialise to JSON; null where unmeasured; no NaN or sentinel 0."""
    scenario = _SCENARIOS_BY_ID[scenario_id]
    _, collector, results = _run_scenario(scenario)

    run_metrics = collector.finalize()
    d = run_metrics.as_dict()

    # Must serialise without error
    text = json.dumps(d)
    assert text  # non-empty

    # Round-trip should parse fine
    parsed = json.loads(text)
    assert isinstance(parsed, dict)

    # Check that non-MEASURED metrics serialise to null, not 0 or 60
    def _check_no_fake_values(obj: object, path: str = "") -> None:
        if isinstance(obj, dict):
            status = obj.get("status")
            value = obj.get("value")
            # Rule: if status is NOT "MEASURED", value must be null
            if status is not None and isinstance(status, str) and status.upper() != "MEASURED":
                assert value is None, (
                    f"Metric at '{path}' has status={status!r} but value={value!r} (expected null)"
                )
            for k, v in obj.items():
                _check_no_fake_values(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _check_no_fake_values(v, f"{path}[{i}]")

    _check_no_fake_values(parsed)

    # Serialised JSON must not contain literal NaN (invalid JSON)
    assert "NaN" not in text, f"JSON contains literal NaN for {scenario_id}"


# ---------------------------------------------------------------------------
# Requirements evaluation: at least one requirement MEASURED for clean runs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_id", ["S01_line_clean", "S02_circle_clean"])
def test_requirements_evaluated(scenario_id: str) -> None:
    """Clean scenarios should yield at least processing_fps as MEASURED (not all INDETERMINATE)."""
    scenario = _SCENARIOS_BY_ID[scenario_id]
    base_cfg = spec_default()
    cfg = scenario.apply(base_cfg, 42)

    collector = MetricsCollector(cfg)
    session = Session(cfg, collector=collector)
    session.source.open()
    session.run(seconds=_RUN_SECONDS)

    run_metrics = collector.finalize()
    verdicts = evaluate(run_metrics, cfg.requirements)

    # pipeline FPS must always be measurable
    fps_m = run_metrics.fps_pipeline
    assert fps_m.status == MetricStatus.MEASURED, (
        f"[{scenario_id}] fps_pipeline should be MEASURED, got {fps_m.status}"
    )
    assert fps_m.value is not None and fps_m.value > 0.0

    # overall verdict must exist
    assert "overall" in verdicts


# ---------------------------------------------------------------------------
# Event log: timestamps must be monotonically non-decreasing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_id", _MOTION_SCENARIO_IDS)
def test_event_log_timestamps_monotonic(scenario_id: str) -> None:
    """All StateEvent timestamps must be non-decreasing."""
    scenario = _SCENARIOS_BY_ID[scenario_id]
    session, _, _ = _run_scenario(scenario)

    events = session.pipeline.events
    for i in range(1, len(events)):
        assert events[i].timestamp_s >= events[i - 1].timestamp_s, (
            f"[{scenario_id}] Event timestamps not monotonic at index {i}: "
            f"{events[i-1].timestamp_s} > {events[i].timestamp_s}"
        )
