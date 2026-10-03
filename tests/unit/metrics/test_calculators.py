"""Unit tests with hand-computed synthetic timelines verifying metric calculators."""

from __future__ import annotations

import math

import pytest

from skylock.core.enums import MetricStatus, TrackState
from skylock.core.types import Detection
from skylock.metrics.calculators import (
    calculate_acquisition_time,
    calculate_centering_error,
    calculate_detection_rates,
    calculate_error_stats,
    calculate_fps_and_latency,
    calculate_lock_retention,
    calculate_pointing_error,
    calculate_reacquisition,
    calculate_target_loss_rate,
    calculate_tracking_error,
)


def _make_det(cx: float, cy: float) -> Detection:
    return Detection(cx=cx, cy=cy, area_px=10.0, peak=255.0, snr=20.0, bbox=(0, 0, 4, 4))


def test_calculate_error_stats_hand_computed() -> None:
    """Exact hand-computed summary statistics for array [3.0, 4.0]."""
    errors = [3.0, 4.0]
    stats = calculate_error_stats(errors)
    assert stats.n == 2
    assert stats.mean == pytest.approx(3.5)
    # RMS: sqrt((9 + 16) / 2) = sqrt(12.5)
    assert stats.rms == pytest.approx(math.sqrt(12.5))
    assert stats.max == pytest.approx(4.0)
    # 95th percentile between 3.0 and 4.0
    assert stats.p95 == pytest.approx(3.95)


def test_acquisition_time_hand_computed() -> None:
    """Exact hand-computed acquisition timeline:

    Frame 0: t=0.00, SEARCH, vis=False
    Frame 1: t=0.05, SEARCH, vis=True (first observable)
    Frame 2: t=0.10, ACQUIRE, vis=True
    Frame 3: t=0.15, TRACK, vis=True (first track)
    Frame 4: t=0.20, TRACK, vis=True
    """
    timestamps = [0.0, 0.05, 0.10, 0.15, 0.20]
    states = [
        TrackState.SEARCH,
        TrackState.SEARCH,
        TrackState.ACQUIRE,
        TrackState.TRACK,
        TrackState.TRACK,
    ]
    vis = [False, True, True, True, True]

    from_start, from_obs, success, obs_duration = calculate_acquisition_time(
        timestamps, states, vis
    )

    assert from_start.status == MetricStatus.MEASURED
    assert from_start.value == pytest.approx(0.15)  # 0.15 - 0.0

    assert from_obs.status == MetricStatus.MEASURED
    assert from_obs.value == pytest.approx(0.10)  # 0.15 - 0.05

    assert success.status == MetricStatus.MEASURED
    assert success.value is True

    # 4 visible frames out of 5 frames spanning 0.2s -> dt = 0.05s * 4 = 0.2s
    assert obs_duration == pytest.approx(0.20)


def test_acquisition_never_acquired() -> None:
    """When TRACK is never entered, acquisition must return NOT_ACQUIRED."""
    timestamps = [0.0, 0.1, 0.2]
    states = [TrackState.SEARCH, TrackState.SEARCH, TrackState.SEARCH]
    vis = [True, True, True]

    from_start, from_obs, success, obs_duration = calculate_acquisition_time(
        timestamps, states, vis
    )

    assert from_start.status == MetricStatus.NOT_ACQUIRED
    assert from_start.value is None
    assert from_obs.status == MetricStatus.NOT_ACQUIRED
    assert from_obs.value is None
    assert success.status == MetricStatus.NOT_ACQUIRED
    assert success.value is None
    assert obs_duration == pytest.approx(0.3)


def test_acquisition_no_ground_truth() -> None:
    """When GT is absent (MP4), from_first_observable is NOT_RUN while from_start is MEASURED."""
    timestamps = [0.0, 0.1, 0.2]
    states = [TrackState.SEARCH, TrackState.ACQUIRE, TrackState.TRACK]

    from_start, from_obs, success, obs_duration = calculate_acquisition_time(
        timestamps, states, None
    )

    assert from_start.status == MetricStatus.MEASURED
    assert from_start.value == pytest.approx(0.2)
    assert from_obs.status == MetricStatus.NOT_RUN
    assert from_obs.reason == "Requires ground truth target visibility"
    assert success.status == MetricStatus.MEASURED
    assert success.value is True
    assert obs_duration == 0.0


def test_tracking_error_hand_computed() -> None:
    """Hand-computed tracking error:

    Frame 0: SEARCH -> ignored
    Frame 1: TRACK, est=(100, 100), gt=(103, 104), vis=True -> error = hypot(3, 4) = 5.0
    Frame 2: TRACK, est=(200, 200), gt=(206, 208), vis=True -> error = hypot(6, 8) = 10.0
    Frame 3: TRACK, est=(300, 300), gt=(300, 300), vis=False -> ignored (not visible)
    """
    states = [TrackState.SEARCH, TrackState.TRACK, TrackState.TRACK, TrackState.TRACK]
    estimates = [(100.0, 100.0), (100.0, 100.0), (200.0, 200.0), (300.0, 300.0)]
    gt_pos = [(100.0, 100.0), (103.0, 104.0), (206.0, 208.0), (300.0, 300.0)]
    vis = [True, True, True, False]

    metric = calculate_tracking_error(states, estimates, gt_pos, vis)

    assert metric.status == MetricStatus.MEASURED
    assert metric.value is not None
    assert metric.value.n == 2
    assert metric.value.mean == pytest.approx(7.5)
    # RMS: sqrt((25 + 100) / 2) = sqrt(62.5)
    assert metric.value.rms == pytest.approx(math.sqrt(62.5))
    assert metric.value.max == pytest.approx(10.0)


def test_pointing_error_hand_computed() -> None:
    """Hand-computed pointing error with boresight at (320, 240):

    Frame 0: TRACK, gt=(323, 244), vis=True -> offset = hypot(3, 4) = 5.0
    Frame 1: TRACK, gt=(326, 248), vis=True -> offset = hypot(6, 8) = 10.0
    """
    states = [TrackState.TRACK, TrackState.TRACK]
    gt_pos = [(323.0, 244.0), (326.0, 248.0)]
    vis = [True, True]

    metric = calculate_pointing_error(states, gt_pos, vis, boresight_px=(320.0, 240.0))

    assert metric.status == MetricStatus.MEASURED
    assert metric.value is not None
    assert metric.value.n == 2
    assert metric.value.mean == pytest.approx(7.5)
    assert metric.value.rms == pytest.approx(math.sqrt(62.5))


def test_centering_error_hand_computed() -> None:
    """Hand-computed centering error (estimate to boresight, no GT required):

    Frame 0: TRACK, est=(320, 243) -> err = 3.0
    Frame 1: TRACK, est=(324, 240) -> err = 4.0
    """
    states = [TrackState.TRACK, TrackState.TRACK]
    estimates = [(320.0, 243.0), (324.0, 240.0)]

    metric = calculate_centering_error(states, estimates, boresight_px=(320.0, 240.0))

    assert metric.status == MetricStatus.MEASURED
    assert metric.value is not None
    assert metric.value.n == 2
    assert metric.value.mean == pytest.approx(3.5)
    assert metric.value.rms == pytest.approx(math.sqrt(12.5))


def test_reacquisition_ground_truth_basis_hand_computed() -> None:
    """Hand-computed reacquisition under GT basis:

    Frame 0: t=0.0, TRACK, vis=True
    Frame 1: t=0.1, LOST, vis=False (occlusion starts)
    Frame 2: t=0.2, REACQUIRE, vis=False
    Frame 3: t=0.3, REACQUIRE, vis=True (emergence at t=0.3)
    Frame 4: t=0.4, TRACK, vis=True (recovered to TRACK at t=0.4 -> duration 0.1s)
    """
    timestamps = [0.0, 0.1, 0.2, 0.3, 0.4]
    states = [
        TrackState.TRACK,
        TrackState.LOST,
        TrackState.REACQUIRE,
        TrackState.REACQUIRE,
        TrackState.TRACK,
    ]
    vis = [True, False, False, True, True]

    reacq_metric, success_metric = calculate_reacquisition(
        timestamps, states, vis, reacquire_timeout_s=1.0
    )

    assert reacq_metric.status == MetricStatus.MEASURED
    assert reacq_metric.value is not None
    assert reacq_metric.value.n == 1
    assert reacq_metric.value.basis == "ground_truth"
    assert reacq_metric.value.mean_s == pytest.approx(0.1)
    assert reacq_metric.value.max_s == pytest.approx(0.1)

    assert success_metric.status == MetricStatus.MEASURED
    assert success_metric.value is True


def test_reacquisition_unrecovered_fails() -> None:
    """When a loss event occurs and target emerges but TRACK is never regained, status is FAILED."""
    timestamps = [0.0, 0.1, 0.2, 0.3]
    states = [TrackState.TRACK, TrackState.LOST, TrackState.REACQUIRE, TrackState.REACQUIRE]
    vis = [True, False, True, True]

    reacq_metric, success_metric = calculate_reacquisition(
        timestamps, states, vis, reacquire_timeout_s=1.0
    )

    assert reacq_metric.status == MetricStatus.FAILED
    assert reacq_metric.value is None
    assert success_metric.status == MetricStatus.MEASURED
    assert success_metric.value is False


def test_reacquisition_tracker_only_basis_hand_computed() -> None:
    """When GT is absent, reacquisition measures LOST to TRACK time flagged as tracker_only."""
    timestamps = [0.0, 0.1, 0.2, 0.35]
    states = [TrackState.TRACK, TrackState.LOST, TrackState.REACQUIRE, TrackState.TRACK]

    reacq_metric, success_metric = calculate_reacquisition(
        timestamps, states, None, reacquire_timeout_s=1.0
    )

    assert reacq_metric.status == MetricStatus.MEASURED
    assert reacq_metric.value is not None
    assert reacq_metric.value.basis == "tracker_only"
    # Duration: 0.35 - 0.1 = 0.25s
    assert reacq_metric.value.mean_s == pytest.approx(0.25)
    assert success_metric.status == MetricStatus.MEASURED
    assert success_metric.value is True


def test_reacquisition_no_loss_events() -> None:
    """When tracker remains in TRACK without interruption, reacquisition is NOT_RUN."""
    timestamps = [0.0, 0.1, 0.2]
    states = [TrackState.TRACK, TrackState.TRACK, TrackState.TRACK]
    vis = [True, True, True]

    reacq_metric, success_metric = calculate_reacquisition(
        timestamps, states, vis, reacquire_timeout_s=1.0
    )

    assert reacq_metric.status == MetricStatus.NOT_RUN
    assert reacq_metric.reason == "No loss event occurred"
    assert success_metric.status == MetricStatus.NOT_RUN


def test_target_loss_rate_hand_computed() -> None:
    """Hand-computed target loss rate:

    Frames 0, 1: SEARCH
    Frames 2-9: post-acquisition window (8 frames).
    States in window: 6 TRACK, 1 LOST, 1 REACQUIRE -> 2 non-TRACK frames.
    Loss rate: 2 / 8 = 0.25.
    """
    states = [
        TrackState.SEARCH,
        TrackState.SEARCH,
        TrackState.TRACK,
        TrackState.TRACK,
        TrackState.LOST,
        TrackState.REACQUIRE,
        TrackState.TRACK,
        TrackState.TRACK,
        TrackState.TRACK,
        TrackState.TRACK,
    ]

    metric = calculate_target_loss_rate(states)
    assert metric.status == MetricStatus.MEASURED
    assert metric.value == pytest.approx(0.25)


def test_lock_retention_hand_computed() -> None:
    """Hand-computed lock retention with lock_radius = 5.0 px:

    Frames 0, 1: SEARCH (ignored)
    Frames 2-9 (8 post-acq frames):
    - Frame 2: TRACK, err=3.0 (retained)
    - Frame 3: TRACK, err=4.0 (retained)
    - Frame 4: LOST, err=3.0 (not in TRACK -> not retained)
    - Frame 5: REACQUIRE, err=2.0 (not retained)
    - Frame 6: TRACK, err=6.0 (err > 5.0 -> not retained)
    - Frame 7: TRACK, err=2.0 (retained)
    - Frame 8: TRACK, err=1.0 (retained)
    - Frame 9: TRACK, err=5.0 (retained)
    Retained = 5 / 8 = 0.625.
    """
    states = [
        TrackState.SEARCH,
        TrackState.SEARCH,
        TrackState.TRACK,
        TrackState.TRACK,
        TrackState.LOST,
        TrackState.REACQUIRE,
        TrackState.TRACK,
        TrackState.TRACK,
        TrackState.TRACK,
        TrackState.TRACK,
    ]
    errors = [None, None, 3.0, 4.0, 3.0, 2.0, 6.0, 2.0, 1.0, 5.0]

    metric = calculate_lock_retention(states, errors, lock_radius_px=5.0)
    assert metric.status == MetricStatus.MEASURED
    assert metric.value == pytest.approx(0.625)


def test_detection_rates_hand_computed() -> None:
    """Hand-computed detection rates:

    Total 4 frames:
    - Frame 0: detections=[(10, 10)], gt=(10, 10), vis=True -> matched
    - Frame 1: detections=[], gt=(50, 50), vis=True -> missed
    - Frame 2: detections=[(20, 20)], gt=(100, 100), vis=False -> ignored (not vis)
    - Frame 3: detections=[], gt=(80, 80), vis=True -> missed

    Detection present rate: 2 frames with dets / 4 total = 0.5.
    Detection rate: 1 matched / 3 visible = 1/3 ≈ 0.333333.
    """
    dets = [
        (_make_det(10.0, 10.0),),
        (),
        (_make_det(20.0, 20.0),),
        (),
    ]
    gt_px = [(10.0, 10.0), (50.0, 50.0), (100.0, 100.0), (80.0, 80.0)]
    vis = [True, True, False, True]

    det_rate, det_pres = calculate_detection_rates(
        dets, gt_px, vis, association_gate_px=30.0
    )

    assert det_pres.status == MetricStatus.MEASURED
    assert det_pres.value == pytest.approx(0.5)

    assert det_rate.status == MetricStatus.MEASURED
    assert det_rate.value == pytest.approx(1.0 / 3.0)


def test_fps_and_latency_hand_computed() -> None:
    """Hand-computed FPS and latency:

    Latencies: [10.0, 20.0, 30.0] ms -> sum = 60 ms = 0.06 s.
    N = 3 frames.
    Pipeline FPS: 3 / 0.06 = 50.0 FPS.
    Wall elapsed: 0.1 s -> Wall FPS: 3 / 0.1 = 30.0 FPS.
    Mean latency: 20.0 ms.
    Nominal FPS: 30.0 -> deadline: 33.33 ms -> 0 missed.
    """
    latencies = [10.0, 20.0, 30.0]
    fps_pipe, fps_w, lat_stats, missed = calculate_fps_and_latency(
        latencies, wall_elapsed_s=0.1, nominal_fps=30.0, source_dropped_frames=1
    )

    assert fps_pipe.status == MetricStatus.MEASURED
    assert fps_pipe.value == pytest.approx(50.0)

    assert fps_w.status == MetricStatus.MEASURED
    assert fps_w.value == pytest.approx(30.0)

    assert lat_stats.status == MetricStatus.MEASURED
    assert lat_stats.value is not None
    assert lat_stats.value.mean == pytest.approx(20.0)
    assert lat_stats.value.p50 == pytest.approx(20.0)

    assert missed.status == MetricStatus.MEASURED
    assert missed.value is not None
    assert missed.value.processing_missed == 0
    assert missed.value.source_dropped == 1
