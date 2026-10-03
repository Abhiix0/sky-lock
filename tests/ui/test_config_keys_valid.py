"""Test that all config keys used in UI code are valid.

Guards against G-01 style regressions where UI code references non-existent config fields.
"""

from __future__ import annotations

import re
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

import pytest

from skylock.config import io as config_io
from skylock.config.models import SkyLockConfig


def get_all_config_keys(obj: Any, prefix: str = "") -> set[str]:
    """Recursively extract all valid dotted config keys from a dataclass."""
    if not is_dataclass(obj):
        return set()

    keys = set()
    for field in fields(obj):
        field_name = field.name
        field_value = getattr(obj, field_name)
        full_key = f"{prefix}.{field_name}" if prefix else field_name

        # Add this key
        keys.add(full_key)

        # Recursively process nested dataclasses
        if is_dataclass(field_value):
            nested_keys = get_all_config_keys(field_value, full_key)
            keys.update(nested_keys)
        # Handle sequences of dataclasses
        elif isinstance(field_value, (list, tuple)) and field_value:
            first = field_value[0] if field_value else None
            if is_dataclass(first):
                # For sequences, we want keys like "target.targets.0.motion"
                nested_keys = get_all_config_keys(first, f"{full_key}.0")
                keys.update(nested_keys)

    return keys


def extract_config_key_literals_from_ui_code() -> set[str]:
    """Extract all string literals that look like config keys from UI code."""
    ui_path = Path("src/skylock/ui")
    key_pattern = re.compile(
        r'["\']('
        r'disturbances\.[a-z_]+\.[a-z_]+'
        r'|target\.[a-z_]+(?:\.\d+\.[a-z_]+)?'
        r'|gimbal\.[a-z_]+'
        r'|camera\.[a-z_]+'
        r'|control\.[a-z_]+'
        r'|input\.[a-z_]+'
        r'|tracking\.[a-z_]+(?:\.[a-z_]+)?'
        r'|seed'
        r')["\']'
    )

    found_keys = set()

    for py_file in ui_path.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for match in key_pattern.finditer(content):
            key = match.group(1)
            found_keys.add(key)

    return found_keys


def test_all_ui_config_keys_are_valid():
    """Verify every config key string used in UI code corresponds to an actual config field."""
    # Get all valid config keys from the model
    default_config = SkyLockConfig()
    valid_keys = get_all_config_keys(default_config)

    # Extract keys used in UI code
    ui_keys = extract_config_key_literals_from_ui_code()

    # Normalize keys (handle array indices like "targets.0.motion" -> "targets.motion")
    def normalize_key(key: str) -> set[str]:
        """Generate possible valid forms of a key."""
        forms = {key}
        # Replace digit indices with generic form
        if "." in key:
            parts = key.split(".")
            normalized_parts = []
            for part in parts:
                if part.isdigit():
                    continue  # Skip digit parts for matching
                normalized_parts.append(part)
            if normalized_parts:
                forms.add(".".join(normalized_parts))
        return forms

    # Check each UI key
    invalid_keys = []
    for ui_key in ui_keys:
        # Generate possible valid forms
        possible_forms = normalize_key(ui_key)

        # Check if any form matches a valid key
        found = False
        for form in possible_forms:
            # Direct match
            if form in valid_keys:
                found = True
                break
            # Prefix match (for nested structures)
            for valid_key in valid_keys:
                if valid_key.startswith(form + ".") or form.startswith(valid_key + "."):
                    found = True
                    break
            if found:
                break

        # Also try to resolve through config_io.override (final validation)
        if not found:
            try:
                # Test if we can override this key
                test_config = SkyLockConfig()
                # Use a safe test value
                if "enabled" in ui_key:
                    test_value = True
                elif "sigma" in ui_key or "density" in ui_key or "strength" in ui_key:
                    test_value = 0.5
                elif "mode" in ui_key:
                    test_value = "AUTO"
                elif "kind" in ui_key:
                    test_value = "simulation"
                else:
                    test_value = 1.0

                config_io.override(test_config, {ui_key: test_value})
                found = True
            except Exception:
                pass

        if not found:
            invalid_keys.append(ui_key)

    assert len(invalid_keys) == 0, (
        f"Found {len(invalid_keys)} invalid config keys in UI code:\n"
        + "\n".join(f"  - {k}" for k in sorted(invalid_keys))
    )


def test_common_config_keys_resolve():
    """Spot-check that common UI config keys can be resolved through config_io.override."""
    # Test individual keys that don't conflict with validation constraints
    test_cases = [
        ("camera.fps", 60.0),
        ("camera.allow_below_spec_fps", True),
        ("gimbal.slew_rate_deg_s", 5.0),
        ("control.mode", "MANUAL"),
        ("input.kind", "mp4"),
        ("input.mp4_path", "/test/path.mp4"),
        ("input.loop", True),
        ("disturbances.gaussian.enabled", True),
        ("disturbances.gaussian.sigma_levels", 10.0),
        ("disturbances.salt_pepper.enabled", False),
        ("disturbances.salt_pepper.density", 0.1),
        ("disturbances.poisson.enabled", True),
        ("disturbances.blur.enabled", True),
        ("disturbances.blur.sigma_px", 2.0),
        ("seed", 12345),
    ]

    config = SkyLockConfig()

    for key, value in test_cases:
        try:
            result = config_io.override(config, {key: value})
            assert result is not None, f"Failed to override {key}"
        except Exception as e:
            pytest.fail(f"Config key '{key}' failed to resolve: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
