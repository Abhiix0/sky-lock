"""Synthetic frame generation helpers for vision and tracking unit tests."""

from __future__ import annotations

import math

import numpy as np

from skylock.core.types import Frame


def make_frame(
    size: tuple[int, int] = (480, 640),
    blobs: list[tuple[float, float, float] | tuple[float, float, float, float]] | None = None,
    background: float = 20.0,
    noise_sigma: float = 0.0,
    salt_pepper_density: float = 0.0,
    frame_index: int = 0,
    timestamp_s: float = 0.0,
    seed: int | None = None,
) -> Frame:
    """Generate a synthetic monochrome Frame independent of the simulation subsystem.

    Args:
        size: (height, width) of the sensor frame.
        blobs: List of blobs defined as (cx, cy, size_px) or (cx, cy, size_px, peak_brightness).
        background: Base black level intensity (default 20.0).
        noise_sigma: Optional additive Gaussian noise standard deviation.
        salt_pepper_density: Optional impulse noise density.
        frame_index: Frame sequence index.
        timestamp_s: Frame capture timestamp in seconds.
        seed: Optional RNG seed for deterministic noise.

    Returns:
        Immutable 2-D monochrome uint8 Frame.
    """
    h, w = size
    img = np.full((h, w), float(background), dtype=np.float32)

    if blobs:
        for blob in blobs:
            cx, cy, size_px = blob[0], blob[1], blob[2]
            peak = float(blob[3]) if len(blob) > 3 else 220.0
            radius = size_px / 2.0
            delta_val = peak - background

            # Compute localized bounding box for fast sub-pixel splatting
            x_min = max(0, math.floor(cx - radius - 1.5))
            x_max = min(w, math.ceil(cx + radius + 1.5))
            y_min = max(0, math.floor(cy - radius - 1.5))
            y_max = min(h, math.ceil(cy + radius + 1.5))

            for y in range(y_min, y_max):
                for x in range(x_min, x_max):
                    d = math.hypot(x - cx, y - cy)
                    if d <= radius + 0.5:
                        coverage = max(0.0, min(1.0, radius - d + 0.5))
                        img[y, x] = max(img[y, x], background + delta_val * coverage)

    rng = np.random.default_rng(seed) if seed is not None else np.random.default_rng(42)

    if noise_sigma > 0.0:
        noise = rng.normal(0.0, noise_sigma, size=(h, w)).astype(np.float32)
        img += noise

    if salt_pepper_density > 0.0:
        u = rng.uniform(0.0, 1.0, size=(h, w)).astype(np.float32)
        pepper = u < (salt_pepper_density * 0.5)
        salt = (u >= (salt_pepper_density * 0.5)) & (u < salt_pepper_density)
        img[pepper] = 0.0
        img[salt] = 255.0

    img_uint8 = np.clip(np.round(img), 0, 255).astype(np.uint8)

    return Frame(
        image=img_uint8,
        index=frame_index,
        timestamp_s=timestamp_s,
        source_id="synthetic",
    )
