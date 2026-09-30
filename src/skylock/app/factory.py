"""Component factory for constructing pipelines and sessions from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from skylock.config.models import SkyLockConfig
from skylock.control.controller import PointingController
from skylock.core.enums import InputKind
from skylock.core.interfaces import FrameSource
from skylock.core.pipeline import TrackingPipeline
from skylock.simulation.gimbal import VirtualGimbal
from skylock.simulation.source import SimulationSource

if TYPE_CHECKING:
    from skylock.app.session import Session


def build_pipeline(config: SkyLockConfig) -> TrackingPipeline:
    """Build and initialize a TrackingPipeline instance.

    Args:
        config: Root SkyLock configuration.

    Returns:
        Configured TrackingPipeline.
    """
    return TrackingPipeline(config)


def create_session_components(
    config: SkyLockConfig,
) -> tuple[FrameSource, TrackingPipeline, PointingController]:
    """Create concrete instances of source, pipeline, and controller for a Session.

    Args:
        config: Root SkyLock configuration.

    Returns:
        Tuple of (source, pipeline, controller).
    """
    pipeline = build_pipeline(config)
    controller = PointingController(
        config.control,
        config.camera,
        max_slew_rate_deg_s=config.gimbal.slew_rate_deg_s,
    )

    if config.input.kind == InputKind.SIMULATION:
        gimbal = VirtualGimbal(config.gimbal)
        source: FrameSource = SimulationSource(config, gimbal=gimbal)
    elif config.input.kind == InputKind.MP4:
        raise NotImplementedError(
            "MP4 input source will be implemented in Phase 7. Set input.kind to SIMULATION."
        )
    else:
        raise ValueError(f"Unknown input kind: {config.input.kind}")

    return source, pipeline, controller


def build_session(config: SkyLockConfig) -> Session:
    """Build a complete tracking and control Session from configuration.

    Args:
        config: Root SkyLock configuration.

    Returns:
        Fully initialized Session instance.
    """
    from skylock.app.session import Session

    source, pipeline, controller = create_session_components(config)
    return Session(
        config=config,
        source=source,
        pipeline=pipeline,
        controller=controller,
    )


__all__ = (
    "build_pipeline",
    "build_session",
    "create_session_components",
)
