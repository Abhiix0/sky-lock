"""Application main entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from skylock.app.cli import cli_main
from skylock.config.models import SkyLockConfig


def _run_gui(initial_config: SkyLockConfig | None = None) -> int:
    """Launch GUI with lazy PySide6 import and clear missing-dependency message."""
    try:
        import PySide6  # noqa: F401
    except ImportError:
        print(
            "Error: PySide6 is required to run the GUI.\n"
            "Install it with: pip install 'skylock[gui]'",
            file=sys.stderr,
        )
        return 1

    from skylock.ui.main_window import run_app

    return run_app(initial_config=initial_config)


def main(argv: Sequence[str] | None = None) -> None:
    """Entry point for skylock CLI/GUI."""
    args = list(argv) if argv is not None else sys.argv[1:]
    # All commands (including gui) go through cli_main now
    sys.exit(cli_main(args))


if __name__ == "__main__":
    main()

