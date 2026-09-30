"""Pure mathematical metric calculation functions for SkyLock."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from skylock.core.enums import TrackState
from skylock.core.types import Detection
from skylock.metrics.status import (
    ErrorStats,
    LatencyStats,
    Metric,
    MissedFrames,
    ReacquisitionEvent,
    ReacquisitionSummary,
)


def calculate_error_stats(errors: Sequence[float] | np.ndarray) -> ErrorStats:
    """Compute summary statistics (mean, RMS, p95, max, n) for a sequence of errors.

    Args:
        errors: Sequence of non-negative float error values. Must not be empty.

    Returns:
        ErrorStats instance.
    """
    arr = np.asarray(errors, dtype=np.float64)
    if arr.size == 0:
        raise ValueError("Cannot calculate error stats on empty array")

    mean_val = float(np.mean(arr))
    rms_val = float(np.sqrt(np.mean(arr**2)))
    p95_val = float(np.percentile(arr, 95))
    max_val = float(np.max(arr))
    n_val = arr.size

    return ErrorStats(
        mean=mean_val,
        rms=rms_val,
        p95=p95_val,
        max=max_val,
        n=n_val,
    )


def calculate_acquisition_time(
    timestamps_s: Sequence[float],
    states: Sequence[TrackState],
    target_visible: Sequence[bool] | None,
) -> tuple[Metric[float], Metric[float], Metric[bool], float]:
    """Calculate acquisition time from start, from first observable, and acquisition success.

    Args:
        timestamps_s: Timestamp in seconds for each frame.
        states: Active tracker state for each frame.
        target_visible: Ground truth visibility flag per frame (None if no GT).

    Returns:
        Tuple of (from_start, from_first_observable, successful_acquisition, observable_duration_s).
    """
    n_frames = len(timestamps_s)
    if n_frames == 0:
        return (
            Metric.not_run("No frames processed"),
            Metric.not_run("No frames processed"),
            Metric.not_run("No frames processed"),
            0.0,
        )

    # Observable duration calculation
    observable_duration_s = 0.0
    if target_visible is not None:
        vis_count = sum(1 for v in target_visible if v)
        dt = (timestamps_s[-1] - timestamps_s[0]) / (n_frames - 1) if n_frames > 1 else 1.0 / 30.0
        observable_duration_s = float(vis_count * dt)

    # Locate first frame entering TRACK state
    first_track_idx: int | None = None
    for i, s in enumerate(states):
        if s == TrackState.TRACK:
            first_track_idx = i
            break

    from_start: Metric[float]
    from_obs: Metric[float]
    successful: Metric[bool]

    if first_track_idx is None:
        from_start = Metric.not_acquired("Target was never acquired into TRACK state")
        successful = Metric.not_acquired("Target was never acquired into TRACK state")

        if target_visible is None:
            from_obs = Metric.not_run("Requires ground truth target visibility")
        else:
            first_vis = next((i for i, v in enumerate(target_visible) if v), None)
            if first_vis is None:
                from_obs = Metric.not_run("Target was never visible in field of view")
            else:
                from_obs = Metric.not_acquired("Target was never acquired into TRACK state")

        return from_start, from_obs, successful, observable_duration_s

    # Acquisition achieved
    t_track = timestamps_s[first_track_idx]
    t_start = timestamps_s[0]
    from_start_val = max(0.0, float(t_track - t_start))
    from_start = Metric.measured(from_start_val)
    successful = Metric.measured(True)

    if target_visible is None:
        from_obs = Metric.not_run("Requires ground truth target visibility")
    else:
        first_vis_idx = next((i for i, v in enumerate(target_visible) if v), None)
        if first_vis_idx is None:
            from_obs = Metric.not_run("Target was never visible in field of view")
        else:
            t_vis = timestamps_s[first_vis_idx]
            from_obs_val = max(0.0, float(t_track - t_vis))
            from_obs = Metric.measured(from_obs_val)

    return from_start, from_obs, successful, observable_duration_s


def calculate_tracking_error(
    states: Sequence[TrackState],
    estimates_px: Sequence[tuple[float, float] | None],
    gt_px: Sequence[tuple[float, float] | None] | None,
    gt_visible: Sequence[bool] | None,
) -> Metric[ErrorStats]:
    """Calculate tracking error |estimate - GT| over frames in TRACK with target visible.

    Args:
        states: Sequence of tracker states.
        estimates_px: Sequence of (x, y) pixel estimates (or None).
        gt_px: Sequence of (x, y) ground truth beacon positions (or None if no GT).
        gt_visible: Sequence of ground truth visibility flags (or None if no GT).

    Returns:
        Metric[ErrorStats] representing tracking error distribution.
    """
    if gt_px is None or gt_visible is None:
        return Metric.not_run("Requires ground truth target position")

    n = len(states)
    if n == 0:
        return Metric.not_run("No frames processed")

    errors: list[float] = []
    has_track_state = False

    for k in range(n):
        if states[k] == TrackState.TRACK:
            has_track_state = True
            if gt_visible[k] and estimates_px[k] is not None and gt_px[k] is not None:
                ex, ey = estimates_px[k]  # type: ignore[misc]
                gx, gy = gt_px[k]  # type: ignore[misc]
                err = float(math.hypot(ex - gx, ey - gy))
                errors.append(err)

    if not errors:
        if not has_track_state:
            return Metric.not_acquired("Target was never in TRACK state")
        return Metric.not_run("No valid frames with target visible in TRACK")

    return Metric.measured(calculate_error_stats(errors))


def calculate_pointing_error(
    states: Sequence[TrackState],
    gt_px: Sequence[tuple[float, float] | None] | None,
    gt_visible: Sequence[bool] | None,
    boresight_px: tuple[float, float] = (320.0, 240.0),
) -> Metric[ErrorStats]:
    """Calculate pointing error |GT - boresight| over frames in TRACK with target visible.

    Args:
        states: Sequence of tracker states.
        gt_px: Sequence of (x, y) ground truth beacon positions (or None if no GT).
        gt_visible: Sequence of ground truth visibility flags (or None if no GT).
        boresight_px: Center optical coordinates (cx, cy).

    Returns:
        Metric[ErrorStats] representing pointing error distribution.
    """
    if gt_px is None or gt_visible is None:
        return Metric.not_run("Requires ground truth target position")

    n = len(states)
    if n == 0:
        return Metric.not_run("No frames processed")

    errors: list[float] = []
    has_track_state = False
    cx, cy = boresight_px

    for k in range(n):
        if states[k] == TrackState.TRACK:
            has_track_state = True
            if gt_visible[k] and gt_px[k] is not None:
                gx, gy = gt_px[k]  # type: ignore[misc]
                err = float(math.hypot(gx - cx, gy - cy))
                errors.append(err)

    if not errors:
        if not has_track_state:
            return Metric.not_acquired("Target was never in TRACK state")
        return Metric.not_run("No valid frames with target visible in TRACK")

    return Metric.measured(calculate_error_stats(errors))


def calculate_centering_error(
    states: Sequence[TrackState],
    estimates_px: Sequence[tuple[float, float] | None],
    boresight_px: tuple[float, float] = (320.0, 240.0),
) -> Metric[ErrorStats]:
    """Calculate centering error |estimate - boresight| over frames in TRACK.

    This metric is purely estimate-driven and does not require ground truth.

    Args:
        states: Sequence of tracker states.
        estimates_px: Sequence of (x, y) pixel estimates (or None).
        boresight_px: Center optical coordinates (cx, cy).

    Returns:
        Metric[ErrorStats] representing centering error distribution.
    """
    n = len(states)
    if n == 0:
        return Metric.not_run("No frames processed")

    errors: list[float] = []
    has_track_state = False
    cx, cy = boresight_px

    for k in range(n):
        if states[k] == TrackState.TRACK:
            has_track_state = True
            if estimates_px[k] is not None:
                ex, ey = estimates_px[k]  # type: ignore[misc]
                err = float(math.hypot(ex - cx, ey - cy))
                errors.append(err)

    if not errors:
        if not has_track_state:
            return Metric.not_acquired("Target was never in TRACK state")
        return Metric.not_run("No estimates in TRACK state")

    return Metric.measured(calculate_error_stats(errors))


def calculate_reacquisition(
    timestamps_s: Sequence[float],
    states: Sequence[TrackState],
    gt_visible: Sequence[bool] | None,
    reacquire_timeout_s: float,
) -> tuple[Metric[ReacquisitionSummary], Metric[bool]]:
    """Calculate target reacquisition events and timing.

    Basis:
    - If ground truth is available: measures time from GT reappearance (visible: False -> True)
      after an occlusion to re-entering TRACK.
    - If ground truth is unavailable: measures time from entering LOST state to re-entering TRACK,
      flagged as basis="tracker_only".

    Args:
        timestamps_s: Frame timestamps.
        states: Tracker states per frame.
        gt_visible: Ground truth visibility per frame (or None).
        reacquire_timeout_s: Maximum allowed reacquisition window.

    Returns:
        Tuple of (reacquisition_time_s, successful_reacquisition).
    """
    n = len(timestamps_s)
    if n == 0:
        return (
            Metric.not_run("No frames processed"),
            Metric.not_run("No frames processed"),
        )

    events: list[ReacquisitionEvent] = []
    has_tracked_once = False

    if gt_visible is not None:
        # Basis: Ground truth reappearance
        basis = "ground_truth"
        waiting_for_reappearance = False
        waiting_for_track = False
        t_reappear: float = 0.0

        for k in range(n):
            st = states[k]
            t = timestamps_s[k]
            vis = gt_visible[k]

            if st == TrackState.TRACK:
                has_tracked_once = True

            if has_tracked_once:
                # Detect occlusion transition: visible -> invisible
                if not vis and not waiting_for_reappearance and not waiting_for_track:
                    waiting_for_reappearance = True

                # Detect emergence transition: invisible -> visible
                elif vis and waiting_for_reappearance:
                    waiting_for_reappearance = False
                    waiting_for_track = True
                    t_reappear = t

                # Check recovery to TRACK
                if waiting_for_track and st == TrackState.TRACK:
                    duration = max(0.0, float(t - t_reappear))
                    success = duration <= reacquire_timeout_s
                    events.append(
                        ReacquisitionEvent(
                            duration_s=duration,
                            basis=basis,
                            success=success,
                            t_start=t_reappear,
                            t_end=t,
                        )
                    )
                    waiting_for_track = False

        if waiting_for_track:
            # Reappeared but never reached TRACK
            events.append(
                ReacquisitionEvent(
                    duration_s=None,
                    basis=basis,
                    success=False,
                    t_start=t_reappear,
                    t_end=None,
                )
            )

    else:
        # Basis: Tracker only (LOST entry to TRACK)
        basis = "tracker_only"
        waiting_for_track = False
        t_loss: float = 0.0

        for k in range(n):
            st = states[k]
            t = timestamps_s[k]

            if st == TrackState.TRACK:
                has_tracked_once = True

            if has_tracked_once:
                if st == TrackState.LOST and not waiting_for_track:
                    waiting_for_track = True
                    t_loss = t

                elif waiting_for_track and st == TrackState.TRACK:
                    duration = max(0.0, float(t - t_loss))
                    success = duration <= reacquire_timeout_s
                    events.append(
                        ReacquisitionEvent(
                            duration_s=duration,
                            basis=basis,
                            success=success,
                            t_start=t_loss,
                            t_end=t,
                        )
                    )
                    waiting_for_track = False

        if waiting_for_track:
            events.append(
                ReacquisitionEvent(
                    duration_s=None,
                    basis=basis,
                    success=False,
                    t_start=t_loss,
                    t_end=None,
                )
            )

    if not events:
        return (
            Metric.not_run("No loss event occurred"),
            Metric.not_run("No loss event occurred"),
        )

    # Check for unrecovered events
    if any(e.duration_s is None for e in events):
        return (
            Metric.failed("Target loss event never recovered to TRACK"),
            Metric.measured(False),
        )

    durations = [e.duration_s for e in events if e.duration_s is not None]
    summary = ReacquisitionSummary(
        events=tuple(events),
        mean_s=float(np.mean(durations)),
        max_s=float(np.max(durations)),
        n=len(events),
        basis=basis,
    )
    all_success = all(e.success for e in events)

    return Metric.measured(summary), Metric.measured(all_success)


def calculate_target_loss_rate(states: Sequence[TrackState]) -> Metric[float]:
    """Calculate target loss rate = non-TRACK frames / total post-acquisition frames.

    Args:
        states: Sequence of tracker states per frame.

    Returns:
        Metric[float] representing fractional loss rate in [0.0, 1.0].
    """
    n = len(states)
    if n == 0:
        return Metric.not_run("No frames processed")

    first_track_idx: int | None = None
    for i, s in enumerate(states):
        if s == TrackState.TRACK:
            first_track_idx = i
            break

    if first_track_idx is None:
        return Metric.not_acquired("Target was never acquired into TRACK state")

    post_acquisition_states = states[first_track_idx:]
    n_post = len(post_acquisition_states)
    non_track_count = sum(1 for s in post_acquisition_states if s != TrackState.TRACK)

    rate = float(non_track_count / n_post)
    return Metric.measured(rate)


def calculate_lock_retention(
    states: Sequence[TrackState],
    errors_px: Sequence[float | None],
    lock_radius_px: float,
) -> Metric[float]:
    """Calculate lock retention = frames in TRACK with error <= lock_radius / post-acq frames.

    Args:
        states: Sequence of tracker states per frame.
        errors_px: Pointing error (if GT available) or centering error (if no GT).
        lock_radius_px: Calibrated lock acceptance radius in pixels.

    Returns:
        Metric[float] representing retention fraction in [0.0, 1.0].
    """
    n = len(states)
    if n == 0:
        return Metric.not_run("No frames processed")

    first_track_idx: int | None = None
    for i, s in enumerate(states):
        if s == TrackState.TRACK:
            first_track_idx = i
            break

    if first_track_idx is None:
        return Metric.not_acquired("Target was never acquired into TRACK state")

    n_post = n - first_track_idx
    retained_count = 0

    for k in range(first_track_idx, n):
        err = errors_px[k]
        if states[k] == TrackState.TRACK and err is not None and err <= lock_radius_px:
            retained_count += 1

    retention = float(retained_count / n_post)
    return Metric.measured(retention)


def calculate_detection_rates(
    detections_list: Sequence[Sequence[Detection]],
    gt_px: Sequence[tuple[float, float] | None] | None,
    gt_visible: Sequence[bool] | None,
    association_gate_px: float,
) -> tuple[Metric[float], Metric[float]]:
    """Calculate detection rate near GT and overall detection present rate.

    Args:
        detections_list: Detections output for each frame.
        gt_px: Ground truth target coordinates per frame (or None).
        gt_visible: Ground truth target visibility per frame (or None).
        association_gate_px: Spatial gate radius for associating detections to GT.

    Returns:
        Tuple of (detection_rate, detection_present_rate).
    """
    n = len(detections_list)
    if n == 0:
        return (
            Metric.not_run("No frames processed"),
            Metric.not_run("No frames processed"),
        )

    # 1. Detection present rate (estimate/detector only, no GT required)
    present_count = sum(1 for dets in detections_list if len(dets) > 0)
    det_present_rate = Metric.measured(float(present_count / n))

    # 2. Detection rate against ground truth
    det_rate: Metric[float]
    if gt_px is None or gt_visible is None:
        det_rate = Metric.not_run("Requires ground truth target position")
    else:
        visible_indices = [k for k in range(n) if gt_visible[k] and gt_px[k] is not None]
        if not visible_indices:
            det_rate = Metric.not_run("No frames with ground truth target visible")
        else:
            matched_count = 0
            for k in visible_indices:
                gx, gy = gt_px[k]  # type: ignore[misc]
                dets = detections_list[k]
                if any(math.hypot(d.cx - gx, d.cy - gy) <= association_gate_px for d in dets):
                    matched_count += 1
            det_rate = Metric.measured(float(matched_count / len(visible_indices)))

    return det_rate, det_present_rate


def calculate_fps_and_latency(
    latencies_ms: Sequence[float],
    wall_elapsed_s: float,
    nominal_fps: float,
    source_dropped_frames: int = 0,
) -> tuple[Metric[float], Metric[float], Metric[LatencyStats], Metric[MissedFrames]]:
    """Calculate pipeline and wall FPS, processing latency statistics, and missed frames.

    Args:
        latencies_ms: Pipeline execution latency in milliseconds per frame.
        wall_elapsed_s: Total end-to-end wall clock duration in seconds.
        nominal_fps: Nominal frame cadence (e.g. 30.0).
        source_dropped_frames: Frames dropped by the upstream source/disturbances.

    Returns:
        Tuple of (fps_pipeline, fps_wall, latency_ms, missed_frames).
    """
    n = len(latencies_ms)
    if n == 0:
        return (
            Metric.not_run("No frames processed"),
            Metric.not_run("No frames processed"),
            Metric.not_run("No frames processed"),
            Metric.not_run("No frames processed"),
        )

    # 1. Pipeline FPS = N / sum(latencies_s)
    sum_latency_s = sum(lat / 1000.0 for lat in latencies_ms)
    if sum_latency_s > 0.0:
        fps_pipeline = Metric.measured(float(n / sum_latency_s))
    else:
        fps_pipeline = Metric.failed("Total processing latency was zero")

    # 2. Wall FPS = N / wall_elapsed_s
    if wall_elapsed_s > 0.0:
        fps_wall = Metric.measured(float(n / wall_elapsed_s))
    else:
        fps_wall = Metric.failed("Wall elapsed time was zero")

    # 3. Latency distribution statistics
    lat_arr = np.asarray(latencies_ms, dtype=np.float64)
    lat_stats = LatencyStats(
        mean=float(np.mean(lat_arr)),
        p50=float(np.median(lat_arr)),
        p95=float(np.percentile(lat_arr, 95)),
        max=float(np.max(lat_arr)),
        n=n,
    )
    latency_metric = Metric.measured(lat_stats)

    # 4. Missed frame deadlines (latency > frame period)
    frame_period_ms = (1.0 / nominal_fps) * 1000.0 if nominal_fps > 0.0 else 33.333333
    processing_missed = sum(1 for lat in latencies_ms if lat > frame_period_ms)
    missed = MissedFrames(
        processing_missed=processing_missed,
        source_dropped=source_dropped_frames,
        total_frames=n,
    )
    missed_metric = Metric.measured(missed)

    return fps_pipeline, fps_wall, latency_metric, missed_metric
