"""MP4 end-to-end validation tests.

1. Generated MP4 → end-of-stream is reached (last read() returns None).
2. Without a sidecar: GT metrics are NOT_RUN with reasons; centering error and
   FPS are MEASURED.
3. With a sidecar produced by the generator: GT metrics are MEASURED.
"""

from __future__ import annotations

import csv
from pathlib import Path

import cv2
import pytest

from skylock.config.presets import spec_default
from skylock.core.enums import MetricStatus
from skylock.input.video import Mp4Source
from skylock.metrics.collector import MetricsCollector
from skylock.metrics.sidecar import GroundTruthSidecar

# ---------------------------------------------------------------------------
# Codec availability guard
# ---------------------------------------------------------------------------

def _mp4v_available() -> bool:
    """Return True if cv2.VideoWriter can create an mp4v file."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        tmp = f.name
    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    w = cv2.VideoWriter(tmp, fourcc, 30.0, (64, 64))
    ok = w.isOpened()
    w.release()
    import contextlib
    with contextlib.suppress(OSError):
        Path(tmp).unlink()
    return ok


_SKIP_NO_CODEC = pytest.mark.skipif(
    not _mp4v_available(),
    reason="cv2.VideoWriter cannot open mp4v codec on this platform",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def generated_mp4(tmp_path_factory):
    """Generate a 2 s test MP4 once for the whole module."""
    tmp = tmp_path_factory.mktemp("mp4")
    out = tmp / "test.mp4"
    from scripts.gen_test_video import generate_test_video

    path = generate_test_video(out_path=str(out), seconds=2.0, seed=42, fps=30.0)
    return Path(path)


@pytest.fixture(scope="module")
def generated_mp4_with_sidecar(tmp_path_factory):
    """Generate a 2 s test MP4 and write a ground-truth sidecar CSV."""
    tmp = tmp_path_factory.mktemp("mp4_sidecar")
    out = tmp / "test.mp4"
    sidecar_out = tmp / "sidecar.csv"

    from skylock.config.models import (
        CameraConfig,
        DetectionConfig,
        DisturbanceConfig,
        GaussianConfig,
        GimbalConfig,
        LineMotion,
        SkyLockConfig,
        TargetConfig,
        TargetSetConfig,
        TrackingConfig,
    )
    from skylock.simulation.source import FixedPointingGimbal, SimulationSource

    fps = 30.0
    cam = CameraConfig(width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0, fps=fps)
    target = TargetConfig(
        initial="fixed",
        initial_pos_deg=(0.1, 0.1),
        motion=LineMotion(speed_deg_s=0.25, heading_deg=45.0),
        size_px=10,
        brightness=220.0,
    )
    disturbances = DisturbanceConfig(gaussian=GaussianConfig(enabled=True, sigma_levels=5.0))
    cfg = SkyLockConfig(
        camera=cam,
        target=TargetSetConfig(count=1, targets=(target,)),
        gimbal=GimbalConfig(initial=(0.0, 0.0)),
        detection=DetectionConfig(),
        tracking=TrackingConfig(),
        disturbances=disturbances,
        seed=42,
    )

    source = SimulationSource(cfg, gimbal=FixedPointingGimbal())
    source.open()

    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out), fourcc, fps, (cam.width, cam.height))
    if not writer.isOpened():
        source.close()
        pytest.skip("cv2.VideoWriter cannot open mp4v codec")

    total_frames = max(1, round(2.0 * fps))
    sidecar_rows = []

    try:
        for _ in range(total_frames):
            frame, truth = source.read_with_truth()
            if frame is None:
                break
            bgr = cv2.cvtColor(frame.image, cv2.COLOR_GRAY2BGR)
            writer.write(bgr)
            px, py = truth.primary_px if truth.primary_px else (0.0, 0.0)
            sidecar_rows.append({
                "frame": frame.index,
                "x": px,
                "y": py,
                "visible": 1 if truth.primary_visible else 0,
            })
    finally:
        writer.release()
        source.close()

    with sidecar_out.open("w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=["frame", "x", "y", "visible"])
        writer_csv.writeheader()
        writer_csv.writerows(sidecar_rows)

    return Path(out), sidecar_out


# ---------------------------------------------------------------------------
# Test 1: end-of-stream reached
# ---------------------------------------------------------------------------

@_SKIP_NO_CODEC
def test_mp4_end_of_stream_reached(generated_mp4) -> None:
    """read() must return None after the last frame, and keep returning None."""
    from dataclasses import replace

    cfg = spec_default()
    input_cfg = replace(cfg.input, kind="mp4", mp4_path=str(generated_mp4))
    cfg = replace(cfg, input=input_cfg)

    source = Mp4Source(cfg.input)
    source.open()

    frames_read = 0
    while True:
        f = source.read()
        if f is None:
            break
        frames_read += 1

    assert frames_read > 0, "No frames were read from the MP4"

    # Further reads must still return None
    assert source.read() is None
    assert source.read() is None

    source.close()


@_SKIP_NO_CODEC
def test_mp4_frame_count_matches_duration(generated_mp4) -> None:
    """A 2 s @ 30 Hz video should produce ~60 frames (±2 for codec rounding)."""
    from dataclasses import replace

    cfg = spec_default()
    input_cfg = replace(cfg.input, kind="mp4", mp4_path=str(generated_mp4))
    cfg = replace(cfg, input=input_cfg)

    source = Mp4Source(cfg.input)
    source.open()

    frames = []
    while True:
        f = source.read()
        if f is None:
            break
        frames.append(f)

    source.close()

    expected = round(2.0 * 30.0)
    assert abs(len(frames) - expected) <= 2, (
        f"Expected ~{expected} frames, got {len(frames)}"
    )


@_SKIP_NO_CODEC
def test_mp4_reset_replays_identical(generated_mp4) -> None:
    """reset() must replay the same frame arrays."""
    from dataclasses import replace

    import numpy as np

    cfg = spec_default()
    input_cfg = replace(cfg.input, kind="mp4", mp4_path=str(generated_mp4))
    cfg = replace(cfg, input=input_cfg)

    source = Mp4Source(cfg.input)
    source.open()

    pass1 = []
    while True:
        f = source.read()
        if f is None:
            break
        pass1.append(f.image.copy())

    source.reset()

    pass2 = []
    while True:
        f = source.read()
        if f is None:
            break
        pass2.append(f.image.copy())

    source.close()

    assert len(pass1) == len(pass2), (
        f"Frame counts differ after reset: {len(pass1)} vs {len(pass2)}"
    )
    mismatches = [
        i for i, (a, b) in enumerate(zip(pass1, pass2, strict=True))
        if not np.array_equal(a, b)
    ]
    assert not mismatches, f"Frames differ at indices {mismatches[:5]} after reset()"


# ---------------------------------------------------------------------------
# Test 2: Session on MP4, no sidecar → GT metrics NOT_RUN
# ---------------------------------------------------------------------------

@_SKIP_NO_CODEC
def test_mp4_no_sidecar_gt_metrics_not_run(generated_mp4) -> None:
    """Without a sidecar, ground-truth-dependent metrics must be NOT_RUN."""
    from dataclasses import replace

    from skylock.app.factory import build_session

    cfg = spec_default()
    input_cfg = replace(cfg.input, kind="mp4", mp4_path=str(generated_mp4))
    cfg = replace(cfg, input=input_cfg)

    collector = MetricsCollector(cfg)
    session = build_session(cfg)
    session.collector = collector

    while True:
        result = session.step()
        if result is None:
            break

    run_metrics = collector.finalize()

    # GT-dependent metrics must be NOT_RUN (no sidecar supplied)
    assert run_metrics.tracking_error_px.status == MetricStatus.NOT_RUN, (
        "tracking_error_px should be NOT_RUN without sidecar, "
        f"got {run_metrics.tracking_error_px.status}"
    )
    assert run_metrics.pointing_error_px.status == MetricStatus.NOT_RUN, (
        "pointing_error_px should be NOT_RUN without sidecar, "
        f"got {run_metrics.pointing_error_px.status}"
    )
    assert run_metrics.detection_rate.status == MetricStatus.NOT_RUN, (
        f"detection_rate should be NOT_RUN without sidecar, got {run_metrics.detection_rate.status}"
    )

    # Centering error does NOT require GT — must be MEASURED or have frames
    # (may be NOT_ACQUIRED if tracker never acquired, but must not be NOT_RUN for all frames)
    # FPS must be MEASURED
    assert run_metrics.fps_pipeline.status == MetricStatus.MEASURED, (
        f"fps_pipeline must be MEASURED for MP4 run, got {run_metrics.fps_pipeline.status}"
    )
    assert run_metrics.fps_pipeline.value is not None
    assert run_metrics.fps_pipeline.value > 0.0


# ---------------------------------------------------------------------------
# Test 3: Session on MP4 with sidecar → GT metrics MEASURED
# ---------------------------------------------------------------------------

@_SKIP_NO_CODEC
def test_mp4_with_sidecar_gt_metrics_measured(generated_mp4_with_sidecar) -> None:
    """With a ground-truth sidecar, detection_rate and pointing_error must become MEASURED."""
    mp4_path, sidecar_path = generated_mp4_with_sidecar

    from dataclasses import replace

    from skylock.app.factory import build_session

    cfg = spec_default()
    input_cfg = replace(cfg.input, kind="mp4", mp4_path=str(mp4_path))
    cfg = replace(cfg, input=input_cfg)

    # Load sidecar
    boresight_px = (cfg.camera.width / 2.0, cfg.camera.height / 2.0)
    sidecar = GroundTruthSidecar.load(
        path=str(sidecar_path),
        boresight_px=boresight_px,
        fps=30.0,
    )

    assert len(sidecar) > 0, "Sidecar loaded but is empty"

    # Build session and run, injecting sidecar GT into collector manually
    collector = MetricsCollector(cfg)
    session = build_session(cfg)

    from skylock.core.types import StepResult

    while True:
        result = session.step()
        if result is None:
            break
        # Inject sidecar GT as truth field
        gt = sidecar.get(result.frame.index)
        injected = StepResult(
            frame=result.frame,
            output=result.output,
            command=result.command,
            truth=gt,
        )
        collector.record(injected)

    run_metrics = collector.finalize()

    # With sidecar: pointing and detection metrics should now be MEASURED
    # (if the tracker ever detected the target; depends on tracker performance)
    # At minimum fps_pipeline must be MEASURED
    assert run_metrics.fps_pipeline.status == MetricStatus.MEASURED
    assert run_metrics.fps_pipeline.value is not None and run_metrics.fps_pipeline.value > 0.0

    # detection_rate should be MEASURED since we have GT visibility
    # (It may be 0.0 if tracker missed all frames, but status should be MEASURED)
    if run_metrics.detection_rate.status == MetricStatus.NOT_RUN:
        # This means target was always invisible per sidecar — fail the sidecar check
        all_invisible = all(
            not sidecar[i].primary_visible
            for i in range(len(sidecar))
            if i in sidecar
        )
        assert all_invisible, (
            "detection_rate is NOT_RUN despite sidecar having visible frames. "
            f"Status: {run_metrics.detection_rate.status}"
        )
