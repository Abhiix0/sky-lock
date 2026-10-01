"""Abstract protocols for hardware abstraction and modular tracking components."""

from __future__ import annotations

from typing import Protocol

from skylock.core.enums import InputKind
from skylock.core.types import ControlCommand, Detection, Frame, Pointing


class FrameSource(Protocol):
    """Protocol for video frame sources (simulation or external file)."""

    def open(self) -> None:
        """Initialize or connect to the frame source."""
        ...

    def read(self) -> Frame | None:
        """Fetch next frame in sequence, or return None if stream ended."""
        ...

    def reset(self) -> None:
        """Reset stream position or simulation state to start."""
        ...

    def close(self) -> None:
        """Release underlying resources."""
        ...

    @property
    def width(self) -> int:
        """Frame image width in pixels."""
        ...

    @property
    def height(self) -> int:
        """Frame image height in pixels."""
        ...

    @property
    def fps(self) -> float:
        """Frame capture or generation rate in Hz."""
        ...

    @property
    def source_id(self) -> str:
        """Unique identifier for this frame source."""
        ...

    @property
    def kind(self) -> InputKind:
        """Kind of input (simulation or mp4)."""
        ...


class Detector(Protocol):
    """Protocol for blob and spot detection algorithms."""

    def detect(self, frame: Frame, roi: tuple[int, int, int, int] | None = None) -> list[Detection]:
        """Detect beacon candidate spots in the given frame."""
        ...

    def reset(self) -> None:
        """Reset internal detector state/background estimators."""
        ...


class GimbalPlant(Protocol):
    """Protocol representing the physical gimbal plant (simulated or real)."""

    def command(self, cmd: ControlCommand, dt: float) -> None:
        """Apply rate command for timestep dt."""
        ...

    @property
    def pointing(self) -> Pointing:
        """Current gimbal pointing angles."""
        ...

    def reset(self) -> None:
        """Reset gimbal to home/initial position."""
        ...
