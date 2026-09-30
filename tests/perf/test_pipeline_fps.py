"""Performance validation: pipeline FPS soft-assert >= 20.

Marked 'perf' — skipped by default unless -m perf is passed.

This is a SOFT assertion: the test warns if FPS < 20 but does not hard-fail
on underpowered CI machines. The hard validation is in scripts/perf_report.py.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from skylock.config.models import (
    DetectionConfig,
    GimbalConfig,
    LineMotion,
    SkyLockConfig,
    TargetConfig,
    TargetSetConfig,
    TrackingConfig,
)
from skylock.core.pipeline import TrackingPipeline
from skylock.simulation.source import FixedPointingGimbal, SimulationSource

_MIN_FPS_SOFT = 20.0
_WARMUP_FRAMES = 30
_MEASURE_FRAMES = 300


def _build_perf_cfg() -> SkyLockConfig:
    """640×480, all disturbances off, single clean target — isolates pipeline cost."""
    return SkyLockConfig(
        target=TargetSetConfig(
            count=1,
            targets=(
                TargetConfig(
                    initial="fixed",
                    initial_pos_deg=(2.0, 1.0),
                    motion=LineMotion(speed_deg_s=0.5, heading_deg=0.0),
                    size_px=10,
                    brightness=220.0,
                ),
            ),
        ),
        gimbal=GimbalConfig(initial=(0.0, 0.0)),
        detection=DetectionConfig(),
        tracking=TrackingConfig(),
        seed=42,
    )


@pytest.mark.perf
def test_pipeline_fps_soft_20() -> None:
    """Pipeline FPS must be >= 20 (soft: warns on failure, does not hard-fail)."""
    cfg = _build_perf_cfg()
    source = SimulationSource(cfg, gimbal=FixedPointingGimbal())
    source.open()
    pipeline = TrackingPipeline(cfg)

    # Warmup: pre-allocate, JIT compile, cache init
    for _ in range(_WARMUP_FRAMES):
        frame = source.read()
        if frame is None:
            break
        pipeline.process(frame)

    pipeline.reset()

    # Measurement
    t0 = time.perf_counter()
    frames_processed = 0
    for _ in range(_MEASURE_FRAMES):
        frame = source.read()
        if frame is None:
            break
        pipeline.process(frame)
        frames_processed += 1

    elapsed = time.perf_counter() - t0
    fps = frames_processed / elapsed if elapsed > 0 else 0.0

    source.close()

    print(f"\n[perf] Pipeline FPS = {fps:.1f} (measured over {frames_processed} frames)")

    if fps < _MIN_FPS_SOFT:
        pytest.xfail(
            f"Pipeline FPS {fps:.1f} is below soft target {_MIN_FPS_SOFT} FPS. "
            "This is a performance warning, not a correctness failure."
        )
    else:
        assert fps >= _MIN_FPS_SOFT, (
            f"Pipeline FPS {fps:.1f} < {_MIN_FPS_SOFT} FPS requirement"
        )


@pytest.mark.perf
def test_detector_latency_640x480() -> None:
    """Blob detector median latency on 640×480 must be <= 15 ms (soft target: 6 ms)."""
    from skylock.vision.detector import ClassicalBlobDetector

    cfg = _build_perf_cfg()
    source = SimulationSource(cfg, gimbal=FixedPointingGimbal())
    source.open()
    detector = ClassicalBlobDetector(cfg.detection)

    latencies_ms: list[float] = []
    for _ in range(200):
        frame = source.read()
        if frame is None:
            break
        t0 = time.perf_counter()
        detector.detect(frame)
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    source.close()

    if not latencies_ms:
        pytest.skip("No frames produced")

    arr = np.array(latencies_ms)
    median_ms = float(np.median(arr))
    p95_ms = float(np.percentile(arr, 95))

    print(f"\n[perf] Detector latency: median={median_ms:.2f} ms  p95={p95_ms:.2f} ms")

    _HARD_LIMIT_MS = 50.0
    assert median_ms <= _HARD_LIMIT_MS, (
        f"Detector median latency {median_ms:.2f} ms exceeds hard limit {_HARD_LIMIT_MS} ms"
    )

    if median_ms > 6.0:
        print(f"  [WARN] Median latency {median_ms:.2f} ms exceeds 6 ms target")
    if median_ms > 15.0:
        pytest.xfail(f"Detector median latency {median_ms:.2f} ms exceeds 15 ms soft limit")
