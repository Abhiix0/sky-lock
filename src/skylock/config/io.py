"""Serialization, deserialization, hashing, and override utilities for SkyLock configs."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

from skylock.config.models import (
    AtmosphereConfig,
    BlurConfig,
    CameraConfig,
    CircleMotion,
    ControlConfig,
    DetectionConfig,
    DisturbanceConfig,
    Figure8Motion,
    GaussianConfig,
    GimbalConfig,
    InputConfig,
    JitterConfig,
    KalmanConfig,
    LineMotion,
    MotionConfig,
    PlatformConfig,
    PoissonConfig,
    RandomMotion,
    RequirementsConfig,
    SaltPepperConfig,
    SearchConfig,
    SkyLockConfig,
    TargetConfig,
    TargetSetConfig,
    TrackingConfig,
)
from skylock.config.validation import ConfigError


def _dataclass_to_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        res: dict[str, Any] = {}
        for f in dataclasses.fields(obj):
            val = getattr(obj, f.name)
            res[f.name] = _dataclass_to_dict(val)
        return res
    if isinstance(obj, (list, tuple)):
        return [_dataclass_to_dict(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    return obj


def to_dict(cfg: SkyLockConfig) -> dict[str, Any]:
    """Convert SkyLockConfig tree to a plain Python dictionary."""
    return _dataclass_to_dict(cfg)  # type: ignore[no-any-return]


def _build_motion(data: dict[str, Any]) -> MotionConfig:
    kind = data.get("kind", "line")
    valid_classes: dict[str, type[Any]] = {
        "line": LineMotion,
        "circle": CircleMotion,
        "figure8": Figure8Motion,
        "random": RandomMotion,
    }
    if kind not in valid_classes:
        raise ConfigError([f"Unknown motion kind '{kind}'"])

    cls = valid_classes[kind]
    allowed = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data.keys()) - allowed
    if unknown:
        raise ConfigError([f"Unknown field(s) in {cls.__name__}: {sorted(unknown)}"])

    args = dict(data)
    if "bounds_deg" in args and isinstance(args["bounds_deg"], list):
        args["bounds_deg"] = tuple(args["bounds_deg"])

    if kind == "line":
        return LineMotion(**args)
    if kind == "circle":
        return CircleMotion(**args)
    if kind == "figure8":
        return Figure8Motion(**args)
    if kind == "random":
        return RandomMotion(**args)
    raise ConfigError([f"Unknown motion kind '{kind}'"])


def _build_dataclass(cls: type[Any], data: dict[str, Any]) -> Any:
    allowed = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data.keys()) - allowed
    if unknown:
        raise ConfigError([f"Unknown field(s) in {cls.__name__}: {sorted(unknown)}"])

    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        if f.name not in data:
            continue
        val = data[f.name]

        # Handle specific nested models
        if f.name == "camera" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(CameraConfig, val)
        elif f.name == "gimbal" and isinstance(val, dict):
            g_dict = dict(val)
            for tuple_field in ("pan_limit_deg", "tilt_limit_deg", "initial"):
                if tuple_field in g_dict and isinstance(g_dict[tuple_field], list):
                    g_dict[tuple_field] = tuple(g_dict[tuple_field])
            kwargs[f.name] = _build_dataclass(GimbalConfig, g_dict)
        elif f.name == "motion" and isinstance(val, dict):
            kwargs[f.name] = _build_motion(val)
        elif f.name == "target" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(TargetSetConfig, val)
        elif f.name == "targets" and isinstance(val, list):
            target_list = []
            for t_data in val:
                t_copy = dict(t_data)
                if "motion" in t_copy and isinstance(t_copy["motion"], dict):
                    t_copy["motion"] = _build_motion(t_copy["motion"])
                if "initial_pos_deg" in t_copy and isinstance(t_copy["initial_pos_deg"], list):
                    t_copy["initial_pos_deg"] = tuple(t_copy["initial_pos_deg"])
                if "visibility_windows" in t_copy and isinstance(
                    t_copy["visibility_windows"], list
                ):
                    t_copy["visibility_windows"] = tuple(
                        tuple(w) for w in t_copy["visibility_windows"]
                    )
                target_list.append(_build_dataclass(TargetConfig, t_copy))
            kwargs[f.name] = tuple(target_list)
        elif f.name == "detection" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(DetectionConfig, val)
        elif f.name == "kalman" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(KalmanConfig, val)
        elif f.name == "search" and isinstance(val, dict):
            s_dict = dict(val)
            if "field_of_regard_deg" in s_dict and isinstance(s_dict["field_of_regard_deg"], list):
                s_dict["field_of_regard_deg"] = tuple(s_dict["field_of_regard_deg"])
            kwargs[f.name] = _build_dataclass(SearchConfig, s_dict)
        elif f.name == "tracking" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(TrackingConfig, val)
        elif f.name == "control" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(ControlConfig, val)
        elif f.name == "disturbances" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(DisturbanceConfig, val)
        elif f.name == "salt_pepper" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(SaltPepperConfig, val)
        elif f.name == "gaussian" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(GaussianConfig, val)
        elif f.name == "poisson" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(PoissonConfig, val)
        elif f.name == "camera_jitter" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(JitterConfig, val)
        elif f.name == "platform" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(PlatformConfig, val)
        elif f.name == "atmosphere" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(AtmosphereConfig, val)
        elif f.name == "blur" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(BlurConfig, val)
        elif f.name == "input" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(InputConfig, val)
        elif f.name == "requirements" and isinstance(val, dict):
            kwargs[f.name] = _build_dataclass(RequirementsConfig, val)
        elif isinstance(val, list):
            kwargs[f.name] = tuple(val)
        else:
            kwargs[f.name] = val

    return cls(**kwargs)


def from_dict(d: dict[str, Any]) -> SkyLockConfig:
    """Reconstruct a SkyLockConfig from a dictionary strictly. Unknown keys raise ConfigError."""
    if not isinstance(d, dict):
        raise ConfigError(["Config payload must be a dictionary"])
    return _build_dataclass(SkyLockConfig, d)  # type: ignore[no-any-return]


def to_json(cfg: SkyLockConfig, indent: int | None = 2) -> str:
    """Serialize SkyLockConfig to formatted JSON."""
    return json.dumps(to_dict(cfg), indent=indent, sort_keys=True)


def from_json(s: str) -> SkyLockConfig:
    """Deserialize SkyLockConfig from a JSON string."""
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        raise ConfigError([f"Invalid JSON: {e}"]) from e
    return from_dict(data)


def snapshot(cfg: SkyLockConfig) -> dict[str, Any]:
    """Return a diagnostic snapshot dictionary including values and derived properties."""
    data = to_dict(cfg)
    data["_derived"] = {
        "ifov_h_deg": cfg.camera.ifov_h_deg,
        "ifov_v_deg": cfg.camera.ifov_v_deg,
        "frame_period_s": cfg.camera.frame_period_s,
        "px_per_deg": cfg.camera.px_per_deg,
        "config_hash": config_hash(cfg),
    }
    return data


def config_hash(cfg: SkyLockConfig) -> str:
    """Compute deterministic SHA-256 hash of canonical JSON configuration."""
    canonical_json = json.dumps(to_dict(cfg), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _set_nested(d: dict[str, Any], path: list[str], value: Any) -> None:
    if len(path) == 1:
        d[path[0]] = value
    else:
        first = path[0]
        if first not in d or not isinstance(d[first], dict):
            d[first] = {}
        _set_nested(d[first], path[1:], value)


def override(
    cfg: SkyLockConfig,
    overrides: dict[str, Any] | None = None,
    **kwargs: Any,
) -> SkyLockConfig:
    """Create a new SkyLockConfig with overridden values, re-validating the result.

    Supports dotted paths like 'camera.fps' or 'tracking.search.scan_rate_deg_s'.
    """
    combined: dict[str, Any] = {}
    if overrides:
        combined.update(overrides)
    combined.update(kwargs)

    raw_dict = to_dict(cfg)
    for key, val in combined.items():
        parts = key.split(".")
        _set_nested(raw_dict, parts, val)

    return from_dict(raw_dict)
