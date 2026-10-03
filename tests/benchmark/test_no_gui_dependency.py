"""No-GUI dependency test: benchmark must run without PySide6."""

from __future__ import annotations

import sys
import types

from skylock.benchmark.catalog import builtin_scenarios
from skylock.benchmark.runner import BenchmarkRunner
from skylock.config.models import SkyLockConfig


def test_no_gui_dependency() -> None:
    """Benchmark framework must not import PySide6.

    Stubs PySide6 to raise ImportError to prove no GUI dependency.
    """
    # Save any existing PySide6 modules
    saved: dict[str, types.ModuleType | None] = {}
    pyside_names = [k for k in sys.modules if k.startswith("PySide6")]
    for name in pyside_names:
        saved[name] = sys.modules.pop(name)

    # Install poison module that raises ImportError on any attribute access
    class _PoisonModule(types.ModuleType):
        def __getattr__(self, name: str) -> None:
            raise ImportError(f"PySide6 is deliberately blocked in benchmark tests: {name}")

    poison = _PoisonModule("PySide6")
    sys.modules["PySide6"] = poison  # type: ignore[assignment]
    sys.modules["PySide6.QtWidgets"] = poison  # type: ignore[assignment]
    sys.modules["PySide6.QtCore"] = poison  # type: ignore[assignment]
    sys.modules["PySide6.QtGui"] = poison  # type: ignore[assignment]

    try:
        runner = BenchmarkRunner(base_config=SkyLockConfig())
        s01 = next(s for s in builtin_scenarios() if s.id == "S01_line_clean")
        record = runner.run(s01, seed=42)

        assert record.status == "COMPLETED"
        assert record.frames > 0
    finally:
        # Restore original state
        for name in ["PySide6", "PySide6.QtWidgets", "PySide6.QtCore", "PySide6.QtGui"]:
            if name in saved:
                sys.modules[name] = saved[name]  # type: ignore[assignment]
            else:
                sys.modules.pop(name, None)
