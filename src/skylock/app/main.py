"""Application main entry point."""

import sys

from skylock.app.cli import cli_main


def main() -> None:
    """Entry point for skylock CLI/GUI."""
    sys.exit(cli_main())


if __name__ == "__main__":
    main()
