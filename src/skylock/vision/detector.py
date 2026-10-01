"""Classical computer vision optical beacon blob detector."""

from __future__ import annotations

import cv2
import numpy as np

from skylock.config.models import DetectionConfig
from skylock.core.interfaces import Detector
from skylock.core.types import Detection, Frame
from skylock.vision.centroid import weighted_centroid
from skylock.vision.preprocess import estimate_background_and_threshold


class ClassicalBlobDetector(Detector):
    """Classical thresholding and connected-component optical beacon spot detector.

    Implements the core.interfaces.Detector protocol.
    """

    def __init__(self, config: DetectionConfig) -> None:
        self.config = config

    def detect(
        self,
        frame: Frame,
        roi: tuple[int, int, int, int] | None = None,
    ) -> list[Detection]:
        """Detect optical beacon candidate spots in the given monochrome frame.

        Args:
            frame: Immutable 2-D monochrome uint8 Frame.
            roi: Optional (x, y, w, h) bounding box to constrain processing.

        Returns:
            List of Detection objects sorted by SNR descending, capped at max_blobs.
        """
        diff, binary_mask, sigma_robust, _, (roi_x0, roi_y0) = (
            estimate_background_and_threshold(frame.image, self.config, roi)
        )

        if binary_mask.size == 0 or np.count_nonzero(binary_mask) == 0:
            return []

        # Connected component labeling (8-connectivity)
        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(
            binary_mask, connectivity=8
        )

        if num_labels <= 1:
            return []

        detections: list[Detection] = []
        raw_img = frame.image

        for i in range(1, num_labels):
            area = float(stats[i, cv2.CC_STAT_AREA])
            if not (self.config.min_area_px <= area <= self.config.max_area_px):
                continue

            bw = int(stats[i, cv2.CC_STAT_WIDTH])
            bh = int(stats[i, cv2.CC_STAT_HEIGHT])
            if bw <= 0 or bh <= 0:
                continue

            # 1. Bounding box aspect ratio filter (<= 3.0)
            aspect = max(bw, bh) / max(1, min(bw, bh))
            if aspect > 3.0:
                continue

            # 2. Fill ratio filter (>= 0.4 for solid optical spots)
            fill_ratio = area / float(bw * bh)
            if fill_ratio < 0.4:
                continue

            bx = int(stats[i, cv2.CC_STAT_LEFT])
            by = int(stats[i, cv2.CC_STAT_TOP])

            # Sub-pixel centroid computed strictly on the localized bounding box crop
            diff_crop = diff[by : by + bh, bx : bx + bw]
            cx, cy = weighted_centroid(
                diff_crop, origin=(roi_x0 + bx, roi_y0 + by), background=0.0
            )

            # Peak intensity from raw sensor frame
            full_x = roi_x0 + bx
            full_y = roi_y0 + by
            raw_crop = raw_img[full_y : full_y + bh, full_x : full_x + bw]
            peak = float(np.max(raw_crop)) if raw_crop.size > 0 else 0.0

            # Signal-to-noise ratio
            peak_signal = float(np.max(diff_crop)) if diff_crop.size > 0 else 0.0
            snr = peak_signal / max(1.0, sigma_robust)

            detections.append(
                Detection(
                    cx=float(cx),
                    cy=float(cy),
                    area_px=area,
                    peak=peak,
                    snr=float(snr),
                    bbox=(full_x, full_y, bw, bh),
                )
            )

        # Sort by SNR descending and truncate to max_blobs
        detections.sort(key=lambda d: d.snr, reverse=True)
        return detections[: self.config.max_blobs]

    def reset(self) -> None:
        """Reset internal detector state (stateless for classical pipeline)."""
        pass
