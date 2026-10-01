"""Pure Python configuration model helpers for the UI (no Qt imports).

Provides validated override dictionaries and constants for config editing.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from skylock.config.io import to_dict
from skylock.config.models import (
    CircleMotion,
    Figure8Motion,
    LineMotion,
    RandomMotion,
    SkyLockConfig,
)

# Valid atmosphere modes per PS_SPEC
ATMOSPHERE_MODES = ("clear", "haze", "fog", "rain", "low_light")

# Valid target shapes
SHAPES = ("square", "disc", "gaussian", "cross")

# Valid motion kinds
MOTION_KINDS = ("line", "circle", "figure8", "random")

# Default disturbance magnitudes (applied when enabling a disturbance that's at 0)
DISTURBANCE_DEFAULTS: dict[str, dict[str, Any]] = {
    "gaussian": {"sigma_levels": 10.0},
    "salt_pepper": {"density": 0.005},
    "poisson": {"photon_scale": 10.0},
    "camera_jitter": {"max_px_frame": 10.0, "correlation": 0.5},
    "platform": {"velocity_px_frame": 3.0, "max_px_frame": 10.0},
    "blur": {"sigma_px": 1.0},
    "atmosphere": {"strength": 0.5},
}


def motion_override(kind: str) -> dict[str, Any]:
    """Return a full motion dict for the given kind using dataclass defaults.

    Args:
        kind: One of "line", "circle", "figure8", "random"

    Returns:
        Motion dict ready for use in override(cfg, {"target.targets": [{"motion": result}]})
    """
    if kind == "line":
        motion = LineMotion()
    elif kind == "circle":
        motion = CircleMotion()
    elif kind == "figure8":
        motion = Figure8Motion()
    elif kind == "random":
        motion = RandomMotion()
    else:
        raise ValueError(f"Unknown motion kind: {kind}")

    # Convert to dict and handle tuples
    motion_dict = dataclasses.asdict(motion)
    # Convert tuples to lists for JSON compatibility
    if "bounds_deg" in motion_dict and isinstance(motion_dict["bounds_deg"], tuple):
        motion_dict["bounds_deg"] = list(motion_dict["bounds_deg"])

    return motion_dict


def target_override(
    cfg: SkyLockConfig,
    *,
    size_px: int | None = None,
    shape: str | None = None,
    motion_kind: str | None = None,
    initial: str | None = None,
) -> dict[str, Any]:
    """Build target.targets override dict, editing only the specified fields.

    Preserves brightness, initial_pos_deg, id, visibility_windows from cfg.target.targets[0].
    Only modifies the fields explicitly provided.

    Args:
        cfg: Current config to base changes on
        size_px: New target size (optional)
        shape: New target shape (optional)
        motion_kind: New motion kind (optional)
        initial: New initial mode "fixed" or "random" (optional)

    Returns:
        Override dict like {"target.targets": [modified_target_dict]}
    """
    if not cfg.target.targets:
        raise ValueError("Config has no targets")

    # Get current target as dict
    cfg_dict = to_dict(cfg)
    current_target = cfg_dict["target"]["targets"][0].copy()

    # Apply changes
    if size_px is not None:
        current_target["size_px"] = size_px
    if shape is not None:
        current_target["shape"] = shape
    if motion_kind is not None:
        current_target["motion"] = motion_override(motion_kind)
    if initial is not None:
        current_target["initial"] = initial

    return {"target.targets": [current_target]}


def slew_override(cfg: SkyLockConfig, slew: float) -> dict[str, Any]:
    """Build slew rate override, clamping scan_rate if necessary.

    Args:
        cfg: Current config
        slew: New slew rate in deg/s

    Returns:
        Override dict adjusting both gimbal.slew_rate_deg_s and tracking.search.scan_rate_deg_s
    """
    current_scan_rate = cfg.tracking.search.scan_rate_deg_s
    new_scan_rate = min(current_scan_rate, slew)

    return {
        "gimbal.slew_rate_deg_s": slew,
        "tracking.search.scan_rate_deg_s": new_scan_rate,
    }


def disturbance_toggle_override(
    cfg: SkyLockConfig,
    name: str,
    enabled: bool,
) -> dict[str, Any]:
    """Build disturbance toggle override with default magnitudes when enabling.

    Args:
        cfg: Current config
        name: Disturbance name (gaussian, salt_pepper, poisson, camera_jitter,
              platform, blur, atmosphere)
        enabled: Whether to enable or disable

    Returns:
        Override dict with enabled flag and magnitude defaults if enabling from 0
    """
    if name not in DISTURBANCE_DEFAULTS:
        raise ValueError(f"Unknown disturbance: {name}")

    overrides: dict[str, Any] = {f"disturbances.{name}.enabled": enabled}

    # When enabling, add default magnitudes if current magnitude is 0/clear
    if enabled:
        dist_cfg = getattr(cfg.disturbances, name)
        defaults = DISTURBANCE_DEFAULTS[name]

        # Check if magnitude is currently at 0 or clear
        needs_defaults = (
            (name == "gaussian" and dist_cfg.sigma_levels == 0.0)
            or (name == "salt_pepper" and dist_cfg.density == 0.0)
            or (name == "poisson" and dist_cfg.photon_scale == 1.0)
            or (name == "camera_jitter" and dist_cfg.max_px_frame == 0.0)
            or (name == "platform" and dist_cfg.max_px_frame == 0.0)
            or (name == "blur" and dist_cfg.sigma_px == 0.0)
            or (name == "atmosphere" and dist_cfg.mode == "clear")
        )

        if needs_defaults:
            for key, value in defaults.items():
                overrides[f"disturbances.{name}.{key}"] = value

    return overrides


def atmosphere_override(cfg: SkyLockConfig, mode: str) -> dict[str, Any]:
    """Build atmosphere override with automatic enabled flag and strength default.

    Args:
        cfg: Current config
        mode: Atmosphere mode (clear, haze, fog, rain, low_light)

    Returns:
        Override dict with mode, enabled flag, and strength if needed
    """
    if mode not in ATMOSPHERE_MODES:
        raise ValueError(f"Unknown atmosphere mode: {mode}")

    overrides: dict[str, Any] = {
        "disturbances.atmosphere.mode": mode,
        "disturbances.atmosphere.enabled": (mode != "clear"),
    }

    # Set default strength if enabling and current strength is 0
    if mode != "clear" and cfg.disturbances.atmosphere.strength == 0.0:
        overrides["disturbances.atmosphere.strength"] = 0.5

    return overrides


__all__ = (
    "ATMOSPHERE_MODES",
    "SHAPES",
    "MOTION_KINDS",
    "DISTURBANCE_DEFAULTS",
    "motion_override",
    "target_override",
    "slew_override",
    "disturbance_toggle_override",
    "atmosphere_override",
)
