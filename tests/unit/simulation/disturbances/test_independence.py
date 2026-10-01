"""Unit tests verifying PRNG stream isolation and disturbance component independence."""

import numpy as np

from skylock.config.models import (
    AtmosphereConfig,
    DisturbanceConfig,
    GaussianConfig,
    JitterConfig,
    PoissonConfig,
    SaltPepperConfig,
)
from skylock.simulation.disturbances.base import DisturbanceContext
from skylock.simulation.disturbances.stack import DisturbanceStack


def test_component_stream_independence() -> None:
    """Toggling one component leaves other components' isolated outputs bit-identical."""
    seed = 8888

    # Stack 1: Only Gaussian noise enabled
    cfg1 = DisturbanceConfig(
        gaussian=GaussianConfig(enabled=True, sigma_levels=12.0),
    )
    stack1 = DisturbanceStack(cfg1, seed=seed)

    # Stack 2: Gaussian + Salt&Pepper + Jitter + Poisson + Atmosphere enabled
    cfg2 = DisturbanceConfig(
        gaussian=GaussianConfig(enabled=True, sigma_levels=12.0),
        salt_pepper=SaltPepperConfig(enabled=True, density=0.05),
        camera_jitter=JitterConfig(enabled=True, max_px_frame=10.0),
        poisson=PoissonConfig(enabled=True, photon_scale=0.5),
        atmosphere=AtmosphereConfig(enabled=True, mode="rain", strength=0.5),
    )
    stack2 = DisturbanceStack(cfg2, seed=seed)

    img = np.full((120, 160), 50.0, dtype=np.float32)
    ctx = DisturbanceContext(frame_index=0, timestamp_s=0.0)

    # Isolated Gaussian output from stack 1 and stack 2 must be bit-identical
    gauss1 = stack1.gaussian.apply(img, ctx)
    gauss2 = stack2.gaussian.apply(img, ctx)
    assert np.array_equal(gauss1, gauss2), (
        "Gaussian output altered by enabling other disturbance components"
    )

    # Compare Jitter isolated between Stack 2 and Stack 3 (where only Jitter is enabled)
    cfg3 = DisturbanceConfig(
        camera_jitter=JitterConfig(enabled=True, max_px_frame=10.0),
    )
    stack3 = DisturbanceStack(cfg3, seed=seed)

    for f in range(25):
        t = f / 30.0
        off2 = stack2.camera_jitter.offset_px(f, t)
        off3 = stack3.camera_jitter.offset_px(f, t)
        assert off2 == off3, f"Jitter offset mismatch at frame {f}"

    # Compare Poisson isolated between Stack 2 and Stack 4 (where only Poisson is enabled)
    cfg4 = DisturbanceConfig(
        poisson=PoissonConfig(enabled=True, photon_scale=0.5),
    )
    stack4 = DisturbanceStack(cfg4, seed=seed)
    p2 = stack2.poisson.apply(img, ctx)
    p4 = stack4.poisson.apply(img, ctx)
    assert np.array_equal(p2, p4), (
        "Poisson output altered by presence/absence of other components"
    )
