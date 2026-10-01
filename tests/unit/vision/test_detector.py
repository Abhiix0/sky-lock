"""Unit tests for ClassicalBlobDetector."""

import math

from skylock.config.models import DetectionConfig
from skylock.vision.detector import ClassicalBlobDetector
from tests.helpers.synthetic import make_frame


def test_three_separate_blobs_produce_three_detections() -> None:
    """Three well-separated optical beacons yield exactly three detections."""
    blobs = [
        (100.0, 100.0, 10.0, 220.0),
        (300.0, 200.0, 10.0, 220.0),
        (450.0, 350.0, 10.0, 220.0),
    ]
    frame = make_frame(size=(480, 640), blobs=blobs, background=20.0)
    detector = ClassicalBlobDetector(DetectionConfig())

    detections = detector.detect(frame)
    assert len(detections) == 3, f"Expected 3 detections, got {len(detections)}"

    # Verify positions correspond to the three blobs
    for bx, by, _, _ in blobs:
        found = any(math.hypot(d.cx - bx, d.cy - by) < 1.0 for d in detections)
        assert found, f"Blob at ({bx}, {by}) not matched by detections"


def test_touching_blobs_merged_into_one() -> None:
    """Two touching / merged optical blobs merge into 1 connected component detection."""
    # Two 10px blobs with centers separated by 6 px (touching and overlapping)
    blobs = [
        (200.0, 200.0, 10.0, 220.0),
        (206.0, 200.0, 10.0, 220.0),
    ]
    frame = make_frame(size=(480, 640), blobs=blobs, background=20.0)
    detector = ClassicalBlobDetector(DetectionConfig())

    detections = detector.detect(frame)
    assert len(detections) == 1, f"Expected 1 merged detection, got {len(detections)}"
    # Merged centroid should be midway ~ 203.0
    assert abs(detections[0].cx - 203.0) < 1.0


def test_empty_uniform_frame_returns_empty_list() -> None:
    """Empty or uniform frame returns [] without raising exceptions."""
    frame = make_frame(size=(480, 640), blobs=[], background=20.0)
    detector = ClassicalBlobDetector(DetectionConfig())

    detections = detector.detect(frame)
    assert detections == []


def test_roi_result_equals_full_frame_inside_roi() -> None:
    """ROI constrained detection equals full-frame detection coordinates inside ROI."""
    target_pos = (250.4, 180.6)
    blobs = [(target_pos[0], target_pos[1], 10.0, 220.0)]
    frame = make_frame(size=(480, 640), blobs=blobs, background=20.0)
    detector = ClassicalBlobDetector(DetectionConfig())

    # Full frame detection
    full_dets = detector.detect(frame, roi=None)
    assert len(full_dets) == 1

    # ROI detection centered around target (ROI: 200, 130, 100, 100)
    roi = (200, 130, 100, 100)
    roi_dets = detector.detect(frame, roi=roi)
    assert len(roi_dets) == 1

    full_det = full_dets[0]
    roi_det = roi_dets[0]

    # Sub-pixel centroids should match within 0.1 px
    dist = math.hypot(full_det.cx - roi_det.cx, full_det.cy - roi_det.cy)
    assert dist < 0.1, f"ROI centroid ({roi_det.cx}, {roi_det.cy}) drifted from full {dist:.4f} px"


def test_salt_pepper_defeated_by_median_for_small_blob() -> None:
    """Salt & pepper noise is rejected by median filter and a 5x5 blob survives."""
    blobs = [(150.0, 150.0, 5.0, 220.0)]
    frame = make_frame(
        size=(300, 300),
        blobs=blobs,
        background=20.0,
        salt_pepper_density=0.02,
        seed=777,
    )
    detector = ClassicalBlobDetector(DetectionConfig(median_filter=True))

    detections = detector.detect(frame)
    assert len(detections) >= 1, "5x5 blob was not detected under S&P noise"
    # Primary detection must match target location
    prim = detections[0]
    err = math.hypot(prim.cx - 150.0, prim.cy - 150.0)
    assert err < 1.0, f"Primary detection error {err:.2f} px too large"
