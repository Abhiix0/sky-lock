#!/usr/bin/env python
"""Script entry point for running SkyLock benchmarks.

Usage:
    python scripts/run_benchmark.py --scenarios S01_line_clean --seeds 1 --out runs/smoke
    python scripts/run_benchmark.py --all --seeds 1,2,3 --out runs/full
"""

from __future__ import annotations

import sys

from skylock.app.cli import cli_main

if __name__ == "__main__":
    # Forward all arguments to the bench subcommand
    argv = ["bench"] + sys.argv[1:]
    sys.exit(cli_main(argv))
