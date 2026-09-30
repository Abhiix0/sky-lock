"""Audit test ensuring no fake defaults (or 0, or 60, ?? 0) exist in metrics package."""

from __future__ import annotations

import re
from pathlib import Path


def test_no_fake_fallbacks_in_metrics_source() -> None:
    """Scan all files in src/skylock/metrics for prohibited fallback patterns.

    Legacy code had misleading fallbacks such as `fps || 60` or `procMs || 0`.
    These are strictly forbidden in SkyLock: unmeasured metrics must have status
    NOT_RUN, NOT_ACQUIRED, or FAILED with value None.
    """
    metrics_dir = Path("src/skylock/metrics")
    assert metrics_dir.is_dir(), f"Metrics dir not found: {metrics_dir.resolve()}"

    forbidden_patterns = [
        re.compile(r"\bor\s+0(?!\.)\b"),   # e.g., 'or 0'
        re.compile(r"\bor\s+60\b"),        # e.g., 'or 60'
        re.compile(r"\?\?\s*0\b"),         # JS coalescing syntax
        re.compile(r"\|\|\s*60\b"),        # JS or 60
        re.compile(r"\|\|\s*0\b"),         # JS or 0
    ]

    violations: list[str] = []

    for py_file in metrics_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.splitlines(), start=1):
            # Ignore comments and docstrings
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("*"):
                continue

            for pattern in forbidden_patterns:
                if pattern.search(line):
                    violations.append(f"{py_file}:{line_num}: {line.strip()}")

    assert not violations, (
        "Found prohibited fallback patterns in metrics package:\n"
        + "\n".join(violations)
    )
