"""Catalog validation tests: every scenario's config validates for its seeds."""

from __future__ import annotations

import pytest

from skylock.benchmark.catalog import builtin_scenarios
from skylock.benchmark.scenario import Scenario
from skylock.config.models import SkyLockConfig


def test_catalog_returns_tuple() -> None:
    """builtin_scenarios() must return a tuple (immutable)."""
    result = builtin_scenarios()
    assert isinstance(result, tuple)


def test_catalog_has_expected_count() -> None:
    """Catalog must contain exactly 16 scenarios."""
    result = builtin_scenarios()
    assert len(result) == 16


def test_catalog_unique_ids() -> None:
    """All scenario IDs must be unique."""
    result = builtin_scenarios()
    ids = [s.id for s in result]
    assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"


def test_catalog_no_module_level_mutable() -> None:
    """Each call to builtin_scenarios() must return a fresh tuple."""
    a = builtin_scenarios()
    b = builtin_scenarios()
    assert a is not b  # Different objects
    assert a == b  # Same content


@pytest.mark.parametrize("scenario", builtin_scenarios(), ids=lambda s: s.id)
def test_scenario_config_validates(scenario: Scenario) -> None:
    """Every scenario must produce a valid SkyLockConfig for each of its seeds.

    Skip MP4 scenarios that need a runtime path.
    """
    if scenario.input_kind == "mp4" and not scenario.mp4_path:
        pytest.skip("MP4 scenario requires runtime path")

    base = SkyLockConfig()
    for seed in scenario.seeds:
        cfg = scenario.apply(base, seed)
        # Config construction validates automatically via __post_init__
        assert cfg.seed == seed
        assert isinstance(cfg, SkyLockConfig)


@pytest.mark.parametrize("scenario", builtin_scenarios(), ids=lambda s: s.id)
def test_scenario_has_description(scenario: Scenario) -> None:
    """Every scenario must have a non-empty description."""
    assert len(scenario.description) > 10, f"{scenario.id} has insufficient description"


@pytest.mark.parametrize("scenario", builtin_scenarios(), ids=lambda s: s.id)
def test_scenario_has_tags(scenario: Scenario) -> None:
    """Every scenario must have at least one tag."""
    assert len(scenario.tags) > 0, f"{scenario.id} has no tags"


@pytest.mark.parametrize(
    "scenario",
    [s for s in builtin_scenarios() if s.input_kind == "simulation"],
    ids=lambda s: s.id,
)
def test_simulation_scenario_duration(scenario: Scenario) -> None:
    """Simulation scenarios must have positive duration <= 30 s for test suites."""
    assert scenario.duration_s > 0.0, f"{scenario.id} has non-positive duration"
    assert scenario.duration_s <= 30.0, (
        f"{scenario.id} duration {scenario.duration_s}s too long for tests"
    )
