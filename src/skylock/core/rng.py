"""Deterministic random number generator derivation for SkyLock subsystems."""

from __future__ import annotations

import zlib

import numpy as np


def derive_rng(seed: int, name: str) -> np.random.Generator:
    """Derive an isolated, deterministic NumPy Generator for a named component.

    Uses SeedSequence with entropy from root seed and spawn key derived from component name.
    Guarantee:
    - Same seed + same name produces identical sequence.
    - Different names produce independent sequences regardless of instantiation order.
    """
    spawn_key = (zlib.crc32(name.encode("utf-8")),)
    seq = np.random.SeedSequence(entropy=seed, spawn_key=spawn_key)
    return np.random.default_rng(seq)
