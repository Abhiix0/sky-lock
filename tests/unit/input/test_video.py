"""Unit tests for Mp4Source video decoder, metadata parsing, and error handling."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from skylock.config.models import InputConfig
from skylock.core.errors import SourceError
from skylock.input.video import Mp4Source


def _create_synthetic_video(
    path: Path,
    width: int = 160,
    height: int = 120,
    fps: float = 30.0,
    frame_count: int = 15,
    color_bgr: tuple[int, int, int] | None = None,
) -> Path:
    """Helper creating a valid synthetic MP4 file using OpenCV VideoWriter."""
    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        pytest.skip(f"OpenCV VideoWriter cannot open mp4v on this environment for path: {path}")

    for i in range(frame_count):
        if color_bgr is not None:
            img = np.full((height, width, 3), color_bgr, dtype=np.uint8)
        else:
            # Vary intensity per frame so frames are distinguishable
            level = (i * 15) % 256
            img = np.full((height, width, 3), (level, level, level), dtype=np.uint8)
        writer.write(img)

    writer.release()
    return path


def test_video_metadata_and_frame_count(tmp_path: Path) -> None:
    """Mp4Source reports correct container metadata and decodes exact frame count."""
    video_path = tmp_path / "test_meta.mp4"
    _create_synthetic_video(video_path, width=320, height=240, fps=25.0, frame_count=10)

    cfg = InputConfig(kind="mp4", mp4_path=str(video_path))
    with Mp4Source(cfg) as source:
        assert source.width == 320
        assert source.height == 240
        assert source.fps == pytest.approx(25.0)
        assert source.kind.value == "mp4"

        frames = []
        while True:
            f = source.read()
            if f is None:
                break
            frames.append(f)

        assert len(frames) == 10
        assert source.frames_decoded == 10


def test_strictly_increasing_timestamps(tmp_path: Path) -> None:
    """Decoded frames have strictly increasing timestamps at exact 1/fps intervals."""
    video_path = tmp_path / "test_timing.mp4"
    fps = 30.0
    _create_synthetic_video(video_path, fps=fps, frame_count=12)

    cfg = InputConfig(kind="mp4", mp4_path=str(video_path))
    with Mp4Source(cfg) as source:
        prev_t = -1.0
        for i in range(12):
            frame = source.read()
            assert frame is not None
            assert frame.index == i
            expected_t = i / fps
            assert frame.timestamp_s == pytest.approx(expected_t, abs=1e-6)
            assert frame.timestamp_s > prev_t
            assert frame.pointing is None
            prev_t = frame.timestamp_s


def test_end_of_stream_returns_none_repeatedly(tmp_path: Path) -> None:
    """Reaching end of stream returns None on the final read and every subsequent read."""
    video_path = tmp_path / "test_eos.mp4"
    _create_synthetic_video(video_path, frame_count=3)

    cfg = InputConfig(kind="mp4", mp4_path=str(video_path))
    source = Mp4Source(cfg)
    source.open()

    assert source.read() is not None
    assert source.read() is not None
    assert source.read() is not None

    # End of stream
    assert source.read() is None
    # Subsequent calls must continue returning None
    assert source.read() is None
    assert source.read() is None
    source.close()


def test_reset_replays_identical_arrays(tmp_path: Path) -> None:
    """reset() seeks back to start and yields identical pixel arrays on second read."""
    video_path = tmp_path / "test_reset.mp4"
    _create_synthetic_video(video_path, frame_count=5)

    cfg = InputConfig(kind="mp4", mp4_path=str(video_path))
    source = Mp4Source(cfg)
    source.open()

    first_pass = []
    while True:
        f = source.read()
        if f is None:
            break
        first_pass.append(f.image.copy())

    assert len(first_pass) == 5

    source.reset()

    second_pass = []
    while True:
        f = source.read()
        if f is None:
            break
        second_pass.append(f.image.copy())

    assert len(second_pass) == 5

    for img1, img2 in zip(first_pass, second_pass, strict=True):
        np.testing.assert_array_equal(img1, img2)

    source.close()


def test_missing_and_corrupt_file_raises_source_error(tmp_path: Path) -> None:
    """Missing or non-video files raise SourceError during open()."""
    # 1. Missing file
    missing = tmp_path / "non_existent.mp4"
    src_missing = Mp4Source(InputConfig(kind="mp4", mp4_path=str(missing)))
    with pytest.raises(SourceError, match="does not exist"):
        src_missing.open()

    # 2. Corrupt file (plain text instead of container)
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_text("This is not an mp4 video file.")
    src_corrupt = Mp4Source(InputConfig(kind="mp4", mp4_path=str(corrupt)))
    with pytest.raises(SourceError, match="Failed to open"):
        src_corrupt.open()


def test_colour_patch_grayscale_conversion(tmp_path: Path) -> None:
    """RGB/BGR colour patches are converted to monochrome using standard ITU-R weights."""
    video_path = tmp_path / "test_color.mp4"
    # Pure Green patch: B=0, G=255, R=0
    # Standard grayscale: 0.299*0 + 0.587*255 + 0.114*0 = 149.685 -> ~150
    _create_synthetic_video(video_path, frame_count=2, color_bgr=(0, 255, 0))

    cfg = InputConfig(kind="mp4", mp4_path=str(video_path))
    with Mp4Source(cfg) as source:
        frame = source.read()
        assert frame is not None
        assert frame.image.ndim == 2
        # Allow tiny +/- 3 margin for lossy MP4 compression
        mean_val = float(np.mean(frame.image))
        assert 145.0 <= mean_val <= 155.0


def test_fps_override_handling(tmp_path: Path) -> None:
    """fps_override takes precedence over detected container FPS."""
    video_path = tmp_path / "test_override.mp4"
    _create_synthetic_video(video_path, fps=30.0, frame_count=3)

    cfg = InputConfig(kind="mp4", mp4_path=str(video_path), fps_override=60.0)
    with Mp4Source(cfg) as source:
        assert source.fps == 60.0
        frame = source.read()
        assert frame is not None
        assert frame.timestamp_s == pytest.approx(0.0)
        frame2 = source.read()
        assert frame2 is not None
        assert frame2.timestamp_s == pytest.approx(1.0 / 60.0)
