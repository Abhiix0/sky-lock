"""Unit tests for camera jitter disturbance model."""

from skylock.config.models import JitterConfig
from skylock.simulation.disturbances.jitter import CameraJitter


def test_jitter_hard_bounds_and_determinism() -> None:
    """Test jitter |offset| <= 20 always for max=20, and seed determinism."""
    config = JitterConfig(enabled=True, max_px_frame=20.0, correlation=0.6)
    jitter1 = CameraJitter(config, seed=42)
    jitter2 = CameraJitter(config, seed=42)

    offsets1 = []
    offsets2 = []

    for f in range(200):
        t = f / 30.0
        off1 = jitter1.offset_px(f, t)
        off2 = jitter2.offset_px(f, t)

        assert abs(off1[0]) <= 20.0, f"Frame {f}: dx {off1[0]} exceeded 20.0"
        assert abs(off1[1]) <= 20.0, f"Frame {f}: dy {off1[1]} exceeded 20.0"
        assert off1 == off2, f"Frame {f}: jitter1 {off1} != jitter2 {off2}"

        offsets1.append(off1)
        offsets2.append(off2)

    # Calling reset reproduces identical sequence
    jitter1.reset()
    for f in range(200):
        t = f / 30.0
        off = jitter1.offset_px(f, t)
        assert off == offsets1[f]


def test_jitter_out_of_order_queries() -> None:
    """Test that querying jitter out-of-order returns consistent results."""
    config = JitterConfig(enabled=True, max_px_frame=15.0, correlation=0.5)
    jitter = CameraJitter(config, seed=99)

    # Pre-sample frames sequentially
    seq_offsets = [jitter.offset_px(f, f / 30.0) for f in range(50)]

    # Query out-of-order on a freshly reset instance
    jitter.reset()
    query_order = [20, 5, 45, 0, 12, 49, 10, 30]
    for f in query_order:
        off = jitter.offset_px(f, f / 30.0)
        assert off == seq_offsets[f], f"Out-of-order query at {f} did not match sequential"


def test_jitter_disabled_returns_zero() -> None:
    """Disabled jitter returns (0.0, 0.0)."""
    config = JitterConfig(enabled=False, max_px_frame=20.0)
    jitter = CameraJitter(config, seed=1)
    for f in range(10):
        assert jitter.offset_px(f, f / 30.0) == (0.0, 0.0)
