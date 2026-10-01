"""Unit tests for simulation repeatability and reset invariance under disturbances."""

import hashlib

import numpy as np

from skylock.config.models import (
    AtmosphereConfig,
    DisturbanceConfig,
    GaussianConfig,
    JitterConfig,
    PlatformConfig,
    PoissonConfig,
    SaltPepperConfig,
    SkyLockConfig,
)
from skylock.simulation.source import SimulationSource


def _compute_source_hash(source: SimulationSource, num_frames: int = 60) -> str:
    hasher = hashlib.sha256()
    for _ in range(num_frames):
        frame = source.read()
        assert frame is not None
        hasher.update(frame.image.tobytes())
    return hasher.hexdigest()


def test_simulation_source_disturbed_determinism() -> None:
    """Two SimulationSource instances with disturbances yield identical SHA-256 over 60 frames."""
    cfg = SkyLockConfig(
        disturbances=DisturbanceConfig(
            camera_jitter=JitterConfig(enabled=True, max_px_frame=5.0, correlation=0.5),
            platform=PlatformConfig(enabled=True, velocity_px_frame=(1.5, -0.5)),
            atmosphere=AtmosphereConfig(enabled=True, mode="rain", strength=0.5),
            gaussian=GaussianConfig(enabled=True, sigma_levels=6.0),
            salt_pepper=SaltPepperConfig(enabled=True, density=0.01),
            poisson=PoissonConfig(enabled=True, photon_scale=0.5),
        ),
        seed=424242,
    )

    source1 = SimulationSource(cfg)
    source2 = SimulationSource(cfg)

    hash1 = _compute_source_hash(source1, 60)
    hash2 = _compute_source_hash(source2, 60)

    assert hash1 == hash2, "Identical seed produced divergent disturbed frames"

    # Resetting source1 must reproduce the exact same hash
    source1.reset()
    hash1_after_reset = _compute_source_hash(source1, 60)
    assert hash1_after_reset == hash1, "Reset did not restore identical frame stream"


def test_jitter_only_equals_clean_shifted() -> None:
    """Enabling only jitter matches clean render shifted by the offset."""
    seed = 5555
    jitter_max = 5.0
    cfg_jitter = SkyLockConfig(
        disturbances=DisturbanceConfig(
            camera_jitter=JitterConfig(enabled=True, max_px_frame=jitter_max, correlation=0.0),
        ),
        seed=seed,
    )
    cfg_clean = SkyLockConfig(
        disturbances=DisturbanceConfig(),
        seed=seed,
    )

    src_jitter = SimulationSource(cfg_jitter)
    src_clean = SimulationSource(cfg_clean)

    for f in range(10):
        frame_j, gt_j = src_jitter.read_with_truth()
        t = f / cfg_clean.camera.fps
        off_x, off_y = gt_j.disturbance_offset_px

        # Render clean camera directly with extra_offset_px = (off_x, off_y)
        clean_img_f32, _ = src_clean.camera.render(
            pointing=src_clean.gimbal.pointing,
            t=t,
            targets=src_clean.target_set.targets,
            extra_offset_px=(off_x, off_y),
        )
        clean_uint8 = np.clip(np.round(clean_img_f32), 0, 255).astype(np.uint8)

        assert np.array_equal(frame_j.image, clean_uint8), (
            f"Frame {f}: Jitter frame did not match clean render with offset ({off_x}, {off_y})"
        )
