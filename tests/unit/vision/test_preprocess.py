"""Unit tests for preprocessing, background subtraction, and MAD estimation."""

import numpy as np

from skylock.config.models import DetectionConfig
from skylock.vision.preprocess import estimate_background_and_threshold
from tests.helpers.synthetic import make_frame


def test_median_filter_defeats_salt_pepper_noise() -> None:
    """3x3 median filter suppresses impulse noise while preserving 5x5 blob."""
    frame = make_frame(
        size=(100, 100),
        blobs=[(50.0, 50.0, 5.0, 220.0)],
        background=20.0,
        salt_pepper_density=0.03,
        seed=101,
    )
    cfg = DetectionConfig(median_filter=True, blur_sigma=1.0)
    diff, mask, sigma_rob, thresh, _ = estimate_background_and_threshold(frame.image, cfg)

    # 5x5 blob must be preserved in the binary mask
    assert mask[50, 50] == 1, "5x5 beacon spot was erased by median filter"

    # Extreme noise spikes elsewhere in background should be cleaned
    # Check that mask has very few or zero isolated false positive pixels
    total_active_px = int(np.sum(mask))
    assert total_active_px < 50, f"Expected < 50 active pixels, got {total_active_px}"


def test_uniform_frame_produces_empty_mask() -> None:
    """Completely uniform image produces an all-zero binary mask without exceptions."""
    img = np.full((120, 160), 20, dtype=np.uint8)
    cfg = DetectionConfig()
    diff, mask, sigma_rob, thresh, _ = estimate_background_and_threshold(img, cfg)

    assert np.all(mask == 0)
    assert np.all(diff == 0.0)
