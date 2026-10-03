"""Video file probing utility using cv2.VideoCapture.

Provides metadata extraction without importing cv2 in UI modules.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VideoInfo:
    """Probed metadata for a video file."""

    width: int
    height: int
    fps: float | None
    frame_count: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        """True if the probe succeeded with valid dimensions."""
        return self.error is None and self.width > 0 and self.height > 0


def probe_video(path: str | Path) -> VideoInfo:
    """Probe a video file and return its metadata.

    Uses cv2.VideoCapture to extract width, height, fps, and frame_count.
    Returns a VideoInfo with error set if the file cannot be read.

    Args:
        path: Path to the video file.

    Returns:
        VideoInfo with extracted metadata or error description.
    """
    import cv2

    p = Path(path)
    if not p.exists() or not p.is_file():
        return VideoInfo(width=0, height=0, fps=None, frame_count=0, error=f"File not found: {p}")

    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        cap.release()
        return VideoInfo(
            width=0, height=0, fps=None, frame_count=0,
            error=f"Cannot open video file: {p}",
        )

    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        raw_fps = cap.get(cv2.CAP_PROP_FPS)
        if raw_fps is None or math.isnan(raw_fps) or math.isinf(raw_fps) or raw_fps <= 0.0:
            fps = None
        else:
            fps = float(raw_fps)

        raw_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_count = raw_count if raw_count > 0 else 0

        if width <= 0 or height <= 0:
            return VideoInfo(
                width=width, height=height, fps=fps, frame_count=frame_count,
                error=f"Invalid video dimensions {width}x{height}",
            )

        return VideoInfo(width=width, height=height, fps=fps, frame_count=frame_count)
    finally:
        cap.release()


__all__ = ("VideoInfo", "probe_video")
