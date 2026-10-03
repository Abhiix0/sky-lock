"""Tests for skylock.detector — OpenCV blob detector."""

import numpy as np
import pytest

from skylock.config import DetectorConfig
from skylock.detector import Detector


class TestDetector:
    """Test the OpenCV blob detector."""

    def test_empty_frame_returns_empty(self):
        detector = Detector()
        result = detector.detect(None)
        assert result["blobs"] == []
        assert result["processing_ms"] == 0.0

    def test_luma_blob_detection(self):
        """Detect a simple white square on a black background using luma mode."""
        config = DetectorConfig(mode="luma", luma_threshold=100)
        detector = Detector(config)

        # Create a black frame (BGR)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        # Draw a 10x10 white square at (45, 45) -> center (50, 50)
        frame[45:55, 45:55] = 255

        result = detector.detect(frame)
        blobs = result["blobs"]

        assert len(blobs) == 1
        blob = blobs[0]

        # Center should be around 49.5 (weighted average of 45..54)
        assert blob["cx"] == pytest.approx(49.5, abs=0.5)
        assert blob["cy"] == pytest.approx(49.5, abs=0.5)
        assert blob["area"] == 100
        assert blob["peak"] == 255.0
        assert blob["snr"] > 0.0

    def test_chroma_blob_detection(self):
        """Detect a magenta square using chroma mode."""
        config = DetectorConfig(mode="chroma", chroma_threshold=100)
        detector = Detector(config)

        # Create a background frame with some noise (BGR)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[..., 1] = 50  # Add some green everywhere

        # Draw a magenta square (B=255, G=0, R=255)
        # Chroma score = min(R, B) - G = min(255, 255) - 0 = 255
        frame[20:30, 20:30, 0] = 255  # Blue
        frame[20:30, 20:30, 1] = 0  # Green (override background)
        frame[20:30, 20:30, 2] = 255  # Red

        result = detector.detect(frame)
        blobs = result["blobs"]

        assert len(blobs) == 1
        blob = blobs[0]

        assert blob["cx"] == pytest.approx(24.5, abs=0.5)
        assert blob["cy"] == pytest.approx(24.5, abs=0.5)
        assert blob["area"] == 100

    def test_roi_detection(self):
        """Detector should only find blobs within the specified ROI."""
        detector = Detector(DetectorConfig(mode="luma", luma_threshold=100))

        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        # Draw blob 1 at (20, 20)
        frame[15:25, 15:25] = 255
        # Draw blob 2 at (80, 80)
        frame[75:85, 75:85] = 255

        # ROI covering only blob 2
        opts = {"roi": {"x": 50, "y": 50, "w": 50, "h": 50}}
        result = detector.detect(frame, opts)
        blobs = result["blobs"]

        assert len(blobs) == 1
        blob = blobs[0]
        assert blob["cx"] > 50
        assert blob["cy"] > 50

    def test_blob_limit(self):
        """Detector should respect the max_blobs option."""
        detector = Detector(DetectorConfig(mode="luma", luma_threshold=100))
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        # Draw 3 blobs
        frame[10:20, 10:20] = 255
        frame[30:40, 30:40] = 255
        frame[50:60, 50:60] = 255

        opts = {"max_blobs": 2}
        result = detector.detect(frame, opts)

        assert len(result["blobs"]) == 2
