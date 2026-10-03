"""Performance benchmark for ClassicalBlobDetector latency."""

import time

import numpy as np
import pytest

from skylock.config.models import DetectionConfig
from skylock.vision.detector import ClassicalBlobDetector
from tests.helpers.synthetic import make_frame


@pytest.mark.perf
def test_detector_latency_640x480() -> None:
    """Measure median detect() latency on 640x480 full frame with noise and beacon."""
    frame = make_frame(
        size=(480, 640),
        blobs=[(320.0, 240.0, 10.0, 220.0)],
        background=20.0,
        noise_sigma=10.0,
        seed=42,
    )
    detector = ClassicalBlobDetector(DetectionConfig())

    # Warmup
    for _ in range(5):
        detector.detect(frame)

    durations: list[float] = []
    for _ in range(40):
        t0 = time.perf_counter()
        dets = detector.detect(frame)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        durations.append(dt_ms)
        assert len(dets) >= 1

    median_latency = float(np.median(durations))
    min_latency = float(np.min(durations))
    max_latency = float(np.max(durations))

    print(
        f"\n[PERF] 640x480 ClassicalBlobDetector: "
        f"median={median_latency:.2f} ms, min={min_latency:.2f} ms, max={max_latency:.2f} ms"
    )

    # Acceptance requirement: target <= 6 ms (soft assert <= 15 ms)
    assert median_latency <= 15.0, f"Detector latency {median_latency:.2f} ms exceeded 15 ms limit"
