"""Unit tests for deterministic RNG derivation."""

import numpy as np

from skylock.core.rng import derive_rng


def test_rng_determinism_same_seed_and_name() -> None:
    rng1 = derive_rng(42, "target.initial")
    rng2 = derive_rng(42, "target.initial")

    vals1 = rng1.standard_normal(10)
    vals2 = rng2.standard_normal(10)

    np.testing.assert_array_equal(vals1, vals2)


def test_rng_name_independence() -> None:
    rng_a = derive_rng(42, "component_a")
    rng_b = derive_rng(42, "component_b")

    vals_a = rng_a.standard_normal(10)
    vals_b = rng_b.standard_normal(10)

    assert not np.array_equal(vals_a, vals_b)


def test_rng_creation_order_independence() -> None:
    # Generator A created before B
    _ = derive_rng(100, "sensor")
    rng_b1 = derive_rng(100, "actuator")
    vals_b1 = rng_b1.uniform(0.0, 1.0, 5)

    # Generator B created before A
    rng_b2 = derive_rng(100, "actuator")
    _ = derive_rng(100, "sensor")
    vals_b2 = rng_b2.uniform(0.0, 1.0, 5)

    np.testing.assert_array_equal(vals_b1, vals_b2)
