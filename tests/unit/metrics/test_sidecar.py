"""Unit tests for GroundTruthSidecar CSV parsing."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from skylock.metrics.sidecar import GroundTruthSidecar


def test_sidecar_loading_valid_csv() -> None:
    """GroundTruthSidecar correctly loads frame,x,y,visible CSV."""
    csv_content = """frame,x,y,visible
0,320.0,240.0,1
1,325.5,242.0,true
2,330.0,245.0,0
"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_path = Path(tmp_dir) / "truth.csv"
        csv_path.write_text(csv_content, encoding="utf-8")

        sidecar = GroundTruthSidecar.load(csv_path, boresight_px=(320.0, 240.0), fps=30.0)

        assert len(sidecar) == 3
        assert 0 in sidecar
        assert 1 in sidecar
        assert 2 in sidecar
        assert 3 not in sidecar

        s0 = sidecar.get(0)
        assert s0 is not None
        assert s0.frame_index == 0
        assert s0.primary_visible is True
        assert s0.primary_px == (320.0, 240.0)
        assert s0.boresight_error_px == pytest.approx(0.0)

        s1 = sidecar[1]
        assert s1.primary_visible is True
        assert s1.primary_px == (325.5, 242.0)
        assert s1.timestamp_s == pytest.approx(1.0 / 30.0)

        s2 = sidecar[2]
        assert s2.primary_visible is False
        assert s2.primary_px is None
        assert s2.boresight_error_px is None


def test_sidecar_missing_column_raises() -> None:
    """Missing required column raises ValueError with clear diagnosis."""
    csv_content = """frame,x,y\n0,320,240\n"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        csv_path = Path(tmp_dir) / "bad.csv"
        csv_path.write_text(csv_content, encoding="utf-8")

        with pytest.raises(ValueError, match="Missing required column 'visible'"):
            GroundTruthSidecar.load(csv_path)


def test_sidecar_missing_file_raises() -> None:
    """Non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        GroundTruthSidecar.load("non_existent_file.csv")
