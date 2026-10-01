"""Unit tests for DisturbanceStack pipeline coordination and ordering."""

import numpy as np

from skylock.config.models import (
    AtmosphereConfig,
    DisturbanceConfig,
    GaussianConfig,
    JitterConfig,
    PlatformConfig,
    SkyLockConfig,
)
from skylock.simulation.disturbances.base import DisturbanceContext
from skylock.simulation.disturbances.stack import DisturbanceStack
from skylock.simulation.source import SimulationSource


def test_stack_disabled_noop_bit_identical() -> None:
    """Disabled disturbance stack performs no operations and is bit-identical to clean input."""
    cfg = DisturbanceConfig()
    stack = DisturbanceStack(cfg, seed=42)

    img = np.full((100, 100), 20.0, dtype=np.float32)
    img[50, 50] = 200.0
    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)

    offset = stack.compute_geometric_offset(0, 0.0)
    assert offset == (0.0, 0.0)

    out = stack.apply_photometric(img, ctx)
    assert np.array_equal(out, img)


def test_stack_quantization() -> None:
    """Test quantization rounds and clamps correctly to uint8 [0, 255]."""
    stack = DisturbanceStack(DisturbanceConfig(), seed=1)
    f32_arr = np.array([-10.4, 0.0, 120.4, 120.6, 254.9, 300.2], dtype=np.float32)
    uint8_arr = stack.quantize(f32_arr)

    assert uint8_arr.dtype == np.uint8
    expected = np.array([0, 0, 120, 121, 255, 255], dtype=np.uint8)
    assert np.array_equal(uint8_arr, expected)


def test_stack_pipeline_order() -> None:
    """Test photometric operators execute in configured order."""
    cfg = DisturbanceConfig(
        atmosphere=AtmosphereConfig(enabled=True, mode="haze", strength=0.5),
        gaussian=GaussianConfig(enabled=True, sigma_levels=5.0),
    )
    stack = DisturbanceStack(cfg, seed=777)
    img = np.full((50, 50), 20.0, dtype=np.float32)
    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)

    out = stack.apply_photometric(img, ctx)
    # Haze lifts background by veil (30 * 0.5 = 15 -> ~35), gaussian adds zero-mean noise
    assert float(np.mean(out)) > 30.0


def test_stack_source_integration() -> None:
    """Test SimulationSource records disturbance offset and returns valid Frame."""
    cfg = SkyLockConfig(
        disturbances=DisturbanceConfig(
            camera_jitter=JitterConfig(enabled=True, max_px_frame=5.0, correlation=0.5),
            platform=PlatformConfig(enabled=True, velocity_px_frame=(2.0, 1.0)),
        ),
        seed=100,
    )
    source = SimulationSource(cfg)
    frame, gt = source.read_with_truth()

    assert frame is not None
    assert frame.image.dtype == np.uint8
    assert frame.image.shape == (cfg.camera.height, cfg.camera.width)
    assert not hasattr(frame, "ground_truth")

    # At frame 0, platform motion is (0, 0), jitter may be non-zero
    assert gt.disturbance_offset_px is not None
    assert isinstance(gt.disturbance_offset_px, tuple)
    assert len(gt.disturbance_offset_px) == 2
