"""Unit tests for SimulationSource determinism, reset, and rendering."""

import hashlib

import cv2
import numpy as np

from skylock.config.models import SkyLockConfig, TargetConfig, TargetSetConfig
from skylock.simulation.source import SimulationSource


def _hash_frames(source: SimulationSource, num_frames: int = 60) -> str:
    hasher = hashlib.sha256()
    for _ in range(num_frames):
        frame = source.read()
        assert frame is not None
        hasher.update(frame.image.tobytes())
    return hasher.hexdigest()


def test_simulation_source_determinism_same_seed() -> None:
    cfg1 = SkyLockConfig(seed=42)
    cfg2 = SkyLockConfig(seed=42)

    src1 = SimulationSource(cfg1)
    src2 = SimulationSource(cfg2)

    hash1 = _hash_frames(src1, num_frames=60)
    hash2 = _hash_frames(src2, num_frames=60)

    assert hash1 == hash2


def test_simulation_source_reset_reproducibility() -> None:
    cfg = SkyLockConfig(seed=42)
    src = SimulationSource(cfg)

    hash_run1 = _hash_frames(src, num_frames=60)
    src.reset()
    hash_run2 = _hash_frames(src, num_frames=60)

    assert hash_run1 == hash_run2


def test_three_targets_produce_three_blobs() -> None:
    t1 = TargetConfig(id="t1", initial="fixed", initial_pos_deg=(-0.8, -0.5), brightness=255.0)
    t2 = TargetConfig(id="t2", initial="fixed", initial_pos_deg=(0.0, 0.0), brightness=255.0)
    t3 = TargetConfig(id="t3", initial="fixed", initial_pos_deg=(0.8, 0.5), brightness=255.0)

    cfg = SkyLockConfig(
        target=TargetSetConfig(count=3, targets=(t1, t2, t3)),
        seed=123,
    )

    src = SimulationSource(cfg)
    frame = src.read()
    assert frame is not None

    # Threshold image above background level to count connected components
    bg_level = cfg.camera.background_level
    thresh = (frame.image > (bg_level + 30.0)).astype(np.uint8) * 255

    num_labels, _ = cv2.connectedComponents(thresh)
    # num_labels includes background (label 0) + 3 targets = 4
    assert num_labels == 4, f"Expected 3 target blobs + background, got {num_labels} labels"
