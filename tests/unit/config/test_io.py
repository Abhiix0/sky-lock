"""Unit tests for configuration I/O, serialization, hashing, and overrides."""

import pytest

from skylock.config.io import (
    config_hash,
    from_dict,
    from_json,
    override,
    snapshot,
    to_dict,
    to_json,
)
from skylock.config.models import SkyLockConfig
from skylock.config.validation import ConfigError


def test_dict_roundtrip() -> None:
    cfg = SkyLockConfig()
    d = to_dict(cfg)
    restored = from_dict(d)
    assert restored == cfg


def test_json_roundtrip() -> None:
    cfg = SkyLockConfig()
    json_str = to_json(cfg)
    restored = from_json(json_str)
    assert restored == cfg


def test_unknown_key_raises_config_error() -> None:
    d = to_dict(SkyLockConfig())
    d["camera"]["non_existent_key"] = 123
    with pytest.raises(ConfigError) as exc_info:
        from_dict(d)
    assert any("Unknown field" in v for v in exc_info.value.violations)


def test_config_hash_stability_and_sensitivity() -> None:
    cfg1 = SkyLockConfig(seed=42)
    cfg2 = SkyLockConfig(seed=42)
    cfg3 = SkyLockConfig(seed=43)

    hash1 = config_hash(cfg1)
    hash2 = config_hash(cfg2)
    hash3 = config_hash(cfg3)

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 64  # SHA-256 hex string


def test_override_dotted_path() -> None:
    cfg = SkyLockConfig()
    overridden = override(cfg, {"camera.fps": 60.0})
    assert overridden.camera.fps == 60.0
    assert overridden.camera.width == 640  # other fields preserved

    # Invalid override raises ConfigError
    with pytest.raises(ConfigError):
        override(cfg, {"camera.fps": 10.0})  # below spec


def test_snapshot_contents() -> None:
    cfg = SkyLockConfig()
    snap = snapshot(cfg)
    assert "_derived" in snap
    derived = snap["_derived"]
    assert derived["ifov_h_deg"] == pytest.approx(0.00625)
    assert derived["ifov_v_deg"] == pytest.approx(0.00625)
    assert "config_hash" in derived
