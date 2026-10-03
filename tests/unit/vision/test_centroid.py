"""Unit tests for sub-pixel intensity-weighted centroid computation."""

import math

import numpy as np

from skylock.vision.centroid import weighted_centroid


def test_centroid_accuracy_sizes_5_10_20() -> None:
    """Sub-pixel centroid error must be < 0.15 px for beacon spot sizes 5, 10, and 20."""
    subpixel_offsets = [(0.15, 0.25), (0.45, -0.35), (-0.2, 0.4), (0.0, 0.0)]

    for size_px in (5, 10, 20):
        radius = size_px / 2.0
        for dx_sub, dy_sub in subpixel_offsets:
            true_cx = 50.0 + dx_sub
            true_cy = 50.0 + dy_sub

            # Generate synthetic patch around spot
            x0 = math.floor(true_cx - radius - 3)
            y0 = math.floor(true_cy - radius - 3)
            w = math.ceil(true_cx + radius + 3) - x0
            h = math.ceil(true_cy + radius + 3) - y0

            crop = np.full((h, w), 20.0, dtype=np.float32)

            for y in range(h):
                for x in range(w):
                    px = x0 + x
                    py = y0 + y
                    dist = math.hypot(px - true_cx, py - true_cy)
                    if dist <= radius + 0.5:
                        coverage = max(0.0, min(1.0, radius - dist + 0.5))
                        crop[y, x] += 200.0 * coverage

            calc_cx, calc_cy = weighted_centroid(crop, origin=(x0, y0), background=20.0)
            err = math.hypot(calc_cx - true_cx, calc_cy - true_cy)

            assert err < 0.15, (
                f"Size {size_px} with offset ({dx_sub}, {dy_sub}) "
                f"had centroid error {err:.4f} >= 0.15"
            )


def test_centroid_empty_crop_fallback() -> None:
    """Empty or zero-weight crop falls back gracefully to bounding box center."""
    crop_zeros = np.zeros((10, 10), dtype=np.float32)
    cx, cy = weighted_centroid(crop_zeros, origin=(100, 200), background=0.0)
    assert cx == 104.5
    assert cy == 204.5

    crop_empty = np.zeros((0, 0), dtype=np.float32)
    cx_e, cy_e = weighted_centroid(crop_empty, origin=(50, 60))
    assert cx_e == 50.0
    assert cy_e == 60.0
