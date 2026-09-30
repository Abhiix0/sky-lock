"""Smoke test for skylock package."""

import skylock


def test_smoke() -> None:
    assert hasattr(skylock, "__version__")
    assert skylock.__version__ == "0.1.0"
