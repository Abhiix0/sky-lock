"""MP4 video frame source implementing FrameSource protocol via OpenCV."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import cv2

from skylock.config.models import InputConfig
from skylock.core.enums import InputKind
from skylock.core.errors import SourceError
from skylock.core.interfaces import FrameSource
from skylock.core.types import Frame

logger = logging.getLogger(__name__)


class Mp4Source(FrameSource):
    """Deterministic video frame source decoding local MP4 video files.

    Implements FrameSource. Native frame resolution is strictly preserved.
    Decodes BGR to monochrome uint8 arrays, tracks frame indices and CFR timestamps,
    and logs warnings if container timestamps indicate variable frame rate (VFR).
    """

    def __init__(self, config: InputConfig) -> None:
        """Initialize Mp4Source with input configuration.

        Args:
            config: Input configuration declaring mp4_path and optional fps_override.
        """
        self.config = config
        self.path = Path(config.mp4_path)

        self._cap: cv2.VideoCapture | None = None
        self._is_open: bool = False
        self._fps: float = 0.0
        self._width: int = 0
        self._height: int = 0
        self._frames_expected: int | None = None
        self._frame_index: int = 0
        self._eos_reached: bool = False

    def open(self) -> None:
        """Open video capture and read container stream metadata.

        Raises:
            SourceError: If file is missing, cannot be opened, or has invalid stream metadata.
        """
        if self._is_open and self._cap is not None and self._cap.isOpened():
            return

        if not self.path.exists() or not self.path.is_file():
            raise SourceError(f"Video file does not exist or is not a file: {self.path}")

        cap = cv2.VideoCapture(str(self.path))
        if not cap.isOpened():
            cap.release()
            raise SourceError(f"Failed to open video file with OpenCV: {self.path}")

        # Detect FPS
        raw_fps = cap.get(cv2.CAP_PROP_FPS)
        if self.config.fps_override is not None and self.config.fps_override > 0.0:
            effective_fps = float(self.config.fps_override)
        elif raw_fps is None or math.isnan(raw_fps) or math.isinf(raw_fps) or raw_fps <= 0.0:
            cap.release()
            raise SourceError(
                f"Invalid FPS {raw_fps} detected in video stream and no valid fps_override provided"
            )
        else:
            effective_fps = float(raw_fps)

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            cap.release()
            raise SourceError(f"Invalid video dimensions {width}x{height} for {self.path}")

        raw_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._frames_expected = raw_count if raw_count > 0 else None

        self._cap = cap
        self._fps = effective_fps
        self._width = width
        self._height = height
        self._frame_index = 0
        self._eos_reached = False
        self._is_open = True

    def read(self) -> Frame | None:
        """Decode and return the next video frame.

        Returns:
            Frame with 2-D monochrome uint8 image, or None if end of stream reached.
        """
        if not self._is_open or self._cap is None:
            return None

        if self._eos_reached:
            return None

        ret, frame_raw = self._cap.read()
        if not ret or frame_raw is None:
            self._eos_reached = True
            return None

        # Check variable frame rate (VFR) timestamp drift
        pos_msec = self._cap.get(cv2.CAP_PROP_POS_MSEC)
        if self._frame_index > 0 and pos_msec > 0.0:
            expected_msec = (self._frame_index / self._fps) * 1000.0
            deviation = abs(pos_msec - expected_msec) / expected_msec
            if deviation > 0.20:
                logger.warning(
                    "VFR timing drift detected at frame %d: expected %.1f ms, got %.1f ms "
                    "(%.1f%% deviation)",
                    self._frame_index,
                    expected_msec,
                    pos_msec,
                    deviation * 100.0,
                )

        # Convert to 2-D uint8 monochrome
        if frame_raw.ndim == 3:
            gray = cv2.cvtColor(frame_raw, cv2.COLOR_BGR2GRAY)
        elif frame_raw.ndim == 2:
            gray = frame_raw
        else:
            raise SourceError(f"Unexpected decoded frame dimensions: {frame_raw.shape}")

        timestamp_s = self._frame_index / self._fps

        frame = Frame(
            image=gray,
            index=self._frame_index,
            timestamp_s=timestamp_s,
            source_id=str(self.path),
            pointing=None,
            meta={"decoded_frames": self._frame_index + 1},
        )

        self._frame_index += 1
        return frame

    def reset(self) -> None:
        """Seek back to frame index 0 and reset frame index counter."""
        if not self._is_open or self._cap is None:
            self.open()
            return

        success = self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        if not success:
            # Reopen if seek fails
            self.close()
            self.open()
        else:
            self._frame_index = 0
            self._eos_reached = False

    def close(self) -> None:
        """Release underlying OpenCV VideoCapture resources."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._is_open = False
        self._eos_reached = True

    def __enter__(self) -> Mp4Source:
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @property
    def width(self) -> int:
        """Frame image width in pixels."""
        return self._width

    @property
    def height(self) -> int:
        """Frame image height in pixels."""
        return self._height

    @property
    def fps(self) -> float:
        """Frame capture rate in Hz."""
        return self._fps

    @property
    def source_id(self) -> str:
        """Unique identifier or file path for this video stream."""
        return str(self.path)

    @property
    def kind(self) -> InputKind:
        """Kind of input."""
        return InputKind.MP4

    @property
    def frames_decoded(self) -> int:
        """Total number of frames decoded so far."""
        return self._frame_index

    @property
    def frames_expected(self) -> int | None:
        """Total container frame count if known, otherwise None."""
        return self._frames_expected


__all__ = ("Mp4Source",)
