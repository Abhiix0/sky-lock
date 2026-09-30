"""Configuration editor providing validation and safe immutable updates."""

from __future__ import annotations

from typing import Any

from skylock.config.io import override, to_dict
from skylock.config.models import SkyLockConfig
from skylock.config.validation import ConfigError


class ConfigEditor:
    """Safely applies dot-path overrides to SkyLockConfig with inline validation."""

    def __init__(self, initial_config: SkyLockConfig | None = None) -> None:
        self._current_config = initial_config if initial_config is not None else SkyLockConfig()

    @property
    def config(self) -> SkyLockConfig:
        """Currently active valid configuration."""
        return self._current_config

    def set_config(self, cfg: SkyLockConfig) -> None:
        """Replace active configuration with an externally supplied one."""
        self._current_config = cfg

    def apply_overrides(
        self, overrides: dict[str, Any]
    ) -> tuple[SkyLockConfig | None, list[str]]:
        """Attempt to apply dot-path overrides to the current config.

        Returns:
            Tuple of (new_config, error_violations_list).
            If validation fails, new_config is None and error_violations_list contains messages.
        """
        try:
            new_cfg = override(self._current_config, overrides)
            self._current_config = new_cfg
            return new_cfg, []
        except ConfigError as e:
            return None, list(e.violations)
        except Exception as e:
            return None, [str(e)]

    def to_dict(self) -> dict[str, Any]:
        """Convert current configuration to a plain dictionary."""
        return to_dict(self._current_config)


__all__ = ("ConfigEditor",)
