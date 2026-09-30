"""Image preprocessing, background estimation, and robust adaptive thresholding."""

from __future__ import annotations

import cv2
import numpy as np

from skylock.config.models import DetectionConfig


def estimate_background_and_threshold(
    image: np.ndarray,
    config: DetectionConfig,
    roi: tuple[int, int, int, int] | None = None,
) -> tuple[np.ndarray, np.ndarray, float, float, tuple[int, int]]:
    """Execute preprocessing pipeline, background subtraction, and robust adaptive thresholding.

    Pipeline:
    1. Crop to ROI if specified (clamped to image dimensions).
    2. Optional 3x3 median filter to eliminate impulse/salt-and-pepper noise.
    3. Gaussian blur smoothing with sigma from config.
    4. Background estimation via large box filter (kernel >= 3x max target size).
    5. Background subtraction and zero-clamping: diff = max(0, smoothed - bg).
    6. Robust noise estimation: sigma = 1.4826 * MAD(diff).
    7. Adaptive thresholding: T = max(abs_min_threshold, threshold_k_sigma * sigma).
    8. Binary threshold mask generation.

    Returns:
        (diff_f32, binary_mask, sigma_robust, threshold, (roi_x0, roi_y0))
    """
    h_img, w_img = image.shape[:2]

    if roi is not None:
        rx, ry, rw, rh = roi
        x0 = max(0, min(w_img - 1, rx))
        y0 = max(0, min(h_img - 1, ry))
        x1 = max(x0 + 1, min(w_img, rx + rw))
        y1 = max(y0 + 1, min(h_img, ry + rh))
        work_img = image[y0:y1, x0:x1]
    else:
        x0, y0 = 0, 0
        work_img = image

    wh, ww = work_img.shape[:2]
    if wh == 0 or ww == 0:
        empty_diff = np.zeros((0, 0), dtype=np.float32)
        empty_mask = np.zeros((0, 0), dtype=np.uint8)
        return empty_diff, empty_mask, 0.0, float(config.abs_min_threshold), (x0, y0)

    # 1. Median filter (suppresses single-pixel salt & pepper noise spikes)
    med_filtered = cv2.medianBlur(work_img, 3) if config.median_filter else work_img

    # 2. Gaussian smoothing
    if config.blur_sigma > 0.0:
        smoothed = cv2.GaussianBlur(
            med_filtered,
            (0, 0),
            sigmaX=config.blur_sigma,
            sigmaY=config.blur_sigma,
            borderType=cv2.BORDER_REFLECT,
        )
    else:
        smoothed = med_filtered

    # 3. Background estimation via box filter (kernel >= 3x max beacon dimension of 20 px)
    kw = max(3, min(61, ww))
    kh = max(3, min(61, wh))
    if kw % 2 == 0:
        kw -= 1
    if kh % 2 == 0:
        kh -= 1

    bg = cv2.boxFilter(smoothed, cv2.CV_32F, (kw, kh), borderType=cv2.BORDER_REFLECT)

    # 4. Background subtraction
    diff = np.maximum(0.0, smoothed.astype(np.float32) - bg)

    # 5. Robust noise estimation using Median Absolute Deviation (MAD)
    # Subsample if frame is large to ensure latency <= 6 ms while maintaining high statistical power
    sample = diff[::4, ::4] if diff.size > 20000 else diff

    med_val = float(np.median(sample))
    mad = float(np.median(np.abs(sample - med_val)))
    sigma_robust = 1.4826 * mad

    # 6. Threshold selection
    threshold = max(float(config.abs_min_threshold), float(config.threshold_k_sigma * sigma_robust))

    # 7. Binary mask
    binary_mask = (diff >= threshold).astype(np.uint8)

    return diff, binary_mask, sigma_robust, threshold, (x0, y0)
