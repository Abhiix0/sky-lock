"""Sub-pixel intensity-weighted centroid computation for optical beacon spots."""

from __future__ import annotations

import numpy as np


def weighted_centroid(
    crop: np.ndarray,
    origin: tuple[int, int] = (0, 0),
    background: float = 0.0,
) -> tuple[float, float]:
    """Compute sub-pixel intensity-weighted centroid on a localized bounding box crop.

    Args:
        crop: 2-D array of pixel intensities within the candidate bounding box.
        origin: (x0, y0) offset of the crop's top-left corner in full-frame pixel coordinates.
        background: Baseline background level to subtract from crop pixels.

    Returns:
        (cx, cy) sub-pixel centroid in full-frame coordinates.
    """
    x0, y0 = origin
    h, w = crop.shape[:2]
    if h == 0 or w == 0:
        return (float(x0), float(y0))

    # Weight is positive intensity above background level
    weights = np.maximum(0.0, crop.astype(np.float32) - float(background))
    total_w = float(np.sum(weights))

    if total_w <= 0.0:
        # Fallback to geometric bounding box center
        return (x0 + (w - 1.0) / 2.0, y0 + (h - 1.0) / 2.0)

    ys, xs = np.indices((h, w), dtype=np.float32)
    cx_local = float(np.sum(xs * weights) / total_w)
    cy_local = float(np.sum(ys * weights) / total_w)

    return (x0 + cx_local, y0 + cy_local)
