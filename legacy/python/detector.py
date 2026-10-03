"""
Beacon blob detector.

Replaces the custom union-find detector with OpenCV connected components.
Detects blobs using either luma (grayscale) or chroma (magenta beacon) thresholding.

JS reference: src/tracking/detector.js
"""

from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np

from skylock.config import DETECTOR, DetectorConfig


class Detector:
    """Optical beacon blob detector.

    Args:
        config: Detector configuration.
    """

    def __init__(self, config: DetectorConfig = DETECTOR) -> None:
        self._cfg = config

    def detect(
        self, frame: np.ndarray | None, opts: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Detect beacon blob centroids in the camera frame.

        Args:
            frame: BGR image numpy array of shape (H, W, 3) or None.
            opts: Optional detection options. Keys:
                  - mode: 'chroma' or 'luma'
                  - chroma_threshold: int
                  - luma_threshold: int
                  - roi: dict {'x': int, 'y': int, 'w': int, 'h': int}
                  - min_area_px: int
                  - max_area_px: int
                  - max_blobs: int

        Returns:
            Dict containing:
                - blobs: List of dicts {cx, cy, area, peak, snr, bbox}
                - processing_ms: Processing time in milliseconds
        """
        t0 = time.perf_counter()

        if frame is None or frame.size == 0 or len(frame.shape) < 2:
            return {"blobs": [], "processing_ms": 0.0}

        opts = opts or {}
        height, width = frame.shape[:2]

        mode = opts.get("mode", self._cfg.mode)
        if mode == "chroma":
            threshold_val = opts.get("chroma_threshold", self._cfg.chroma_threshold)
        else:
            threshold_val = opts.get("luma_threshold", self._cfg.luma_threshold)

        # Determine ROI (top-left coordinates)
        min_x, max_x = 0, width - 1
        min_y, max_y = 0, height - 1

        roi = opts.get("roi")
        if roi:
            min_x = max(0, int(roi["x"]))
            max_x = min(width - 1, int(roi["x"] + roi["w"]))
            min_y = max(0, int(roi["y"]))
            max_y = min(height - 1, int(roi["y"] + roi["h"]))

        # Early exit for invalid ROI
        if min_x > max_x or min_y > max_y:
            return {"blobs": [], "processing_ms": 0.0}

        # Calculate background statistics (approximate)
        # Using a subsampled version for speed, similar to JS
        bg_subsample = frame[min_y : max_y + 1 : 16, min_x : max_x + 1 : 16]

        if mode == "chroma" and len(frame.shape) == 3:
            # OpenCV is BGR: frame[..., 0]=B, frame[..., 1]=G, frame[..., 2]=R
            # Chroma score: min(R, B) - G
            # For magenta beacon, R and B are high, G is low
            b = bg_subsample[..., 0].astype(np.int16)
            g = bg_subsample[..., 1].astype(np.int16)
            r = bg_subsample[..., 2].astype(np.int16)
            bg_score = np.minimum(r, b) - g
        else:
            # Luma score
            if len(frame.shape) == 3:
                bg_score = cv2.cvtColor(bg_subsample, cv2.COLOR_BGR2GRAY).astype(np.int16)
            else:
                bg_score = bg_subsample.astype(np.int16)

        bg_mean = float(np.mean(bg_score)) if bg_score.size > 0 else 0.0
        bg_std = float(np.std(bg_score)) if bg_score.size > 0 else 0.0

        # Extract ROI
        roi_frame = frame[min_y : max_y + 1, min_x : max_x + 1]

        # Calculate score image for ROI
        if mode == "chroma" and len(frame.shape) == 3:
            b = roi_frame[..., 0].astype(np.int16)
            g = roi_frame[..., 1].astype(np.int16)
            r = roi_frame[..., 2].astype(np.int16)
            score_img = np.minimum(r, b) - g
        else:
            if len(frame.shape) == 3:
                score_img = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY).astype(np.int16)
            else:
                score_img = roi_frame.astype(np.int16)

        # Thresholding
        _, thresh = cv2.threshold(
            np.clip(score_img, 0, 255).astype(np.uint8),
            threshold_val,
            255,
            cv2.THRESH_BINARY,
        )

        # Connected Components
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            thresh, connectivity=4
        )

        min_area = opts.get("min_area_px", self._cfg.min_area_px)
        max_area = opts.get("max_area_px", self._cfg.max_area_px)
        max_blobs = opts.get("max_blobs", self._cfg.max_blobs)

        denominator_std = max(bg_std, 1.0)
        filtered_blobs = []

        # label 0 is background
        for i in range(1, num_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            if min_area <= area <= max_area:
                # Find peak intensity and weighted centroid
                blob_mask = labels == i
                blob_scores = score_img[blob_mask]
                peak = float(np.max(blob_scores))

                # Weighted centroid calculation within ROI
                y_coords, x_coords = np.nonzero(blob_mask)
                total_weight = np.sum(blob_scores)

                if total_weight > 0:
                    cx = float(np.sum(x_coords * blob_scores) / total_weight)
                    cy = float(np.sum(y_coords * blob_scores) / total_weight)
                else:
                    cx, cy = float(centroids[i, 0]), float(centroids[i, 1])

                # Translate back to full frame coordinates
                cx += min_x
                cy += min_y

                snr = (peak - bg_mean) / denominator_std

                x0 = stats[i, cv2.CC_STAT_LEFT] + min_x
                y0 = stats[i, cv2.CC_STAT_TOP] + min_y
                w = stats[i, cv2.CC_STAT_WIDTH]
                h = stats[i, cv2.CC_STAT_HEIGHT]

                filtered_blobs.append(
                    {
                        "cx": cx,
                        "cy": cy,
                        "area": int(area),
                        "peak": peak,
                        "snr": float(snr),
                        "bbox": {
                            "x0": int(x0),
                            "y0": int(y0),
                            "x1": int(x0 + w - 1),
                            "y1": int(y0 + h - 1),
                        },
                    }
                )

        # Sort by peak descending and limit to max_blobs
        filtered_blobs.sort(key=lambda b: b["peak"], reverse=True)
        filtered_blobs = filtered_blobs[:max_blobs]

        t1 = time.perf_counter()
        processing_ms = (t1 - t0) * 1000.0

        return {
            "blobs": filtered_blobs,
            "processing_ms": processing_ms,
        }
