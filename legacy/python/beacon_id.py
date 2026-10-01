"""
Beacon Identification (Blink Code Matched Filter).

Builds a discrete template from a binary string and computes
the normalized cross-correlation (matched-filter score) against
a candidate's intensity history to identify the true beacon among
noise and glare.

JS reference: src/tracking/beaconId.js
"""

from __future__ import annotations

import math
from typing import Any

from skylock.config import BEACON_CODE, ID_CONFIG, BeaconCodeConfig, IdConfig


def build_code_template(bits: str = "10110010", samples_per_bit: int = 3) -> list[float]:
    """Build the oversampled discrete template vector.

    Args:
        bits: Binary string (e.g. '10110010').
        samples_per_bit: Number of camera frames per bit.

    Returns:
        List of float values (0.0 or 1.0).
    """
    template = []
    for bit in bits:
        val = 1.0 if bit == "1" else 0.0
        for _ in range(samples_per_bit):
            template.append(val)
    return template


def compute_blink_score(
    history: list[float], code_config: BeaconCodeConfig = BEACON_CODE
) -> dict[str, float]:
    """Compute matched-filter correlation score of history against blink code.

    Evaluates all possible cyclic phase shifts.

    Args:
        history: Array of observed intensities (0 = absent/off, >0 = detected).
        code_config: Configuration with bits and samples_per_bit.

    Returns:
        Dict with 'score' in [0, 1] and 'best_shift'.
    """
    bits = code_config.bits
    samples_per_bit = code_config.samples_per_bit
    template = build_code_template(bits, samples_per_bit)
    template_len = len(template)

    if not history or len(history) < template_len:
        return {"score": 0.0, "best_shift": 0.0}

    # Extract most recent samples
    recent = history[-template_len:]

    # Binary thresholding
    bin_signal = [1.0 if val > 0 else 0.0 for val in recent]
    ones_count = sum(bin_signal)

    # Degenerate cases
    if ones_count == 0 or ones_count == template_len:
        return {"score": 0.0, "best_shift": 0.0}

    # Template stats
    mean_t = sum(template) / template_len
    var_t = sum((val - mean_t) ** 2 for val in template)

    # Signal stats
    mean_s = sum(bin_signal) / template_len
    var_s = sum((val - mean_s) ** 2 for val in bin_signal)

    if var_s < 1e-6 or var_t < 1e-6:
        return {"score": 0.0, "best_shift": 0.0}

    denom = math.sqrt(var_s * var_t)

    # Cyclic cross-correlation
    max_score = -1.0
    best_shift = 0

    for shift in range(template_len):
        cross_sum = 0.0
        for i in range(template_len):
            shifted_idx = (i + shift) % template_len
            cross_sum += (bin_signal[i] - mean_s) * (template[shifted_idx] - mean_t)

        r = cross_sum / denom
        if r > max_score:
            max_score = r
            best_shift = shift

    return {
        "score": max(0.0, min(1.0, max_score)),
        "best_shift": float(best_shift),
    }


def evaluate_candidates(
    candidates: list[dict[str, Any]],
    code_config: BeaconCodeConfig = BEACON_CODE,
    id_config: IdConfig = ID_CONFIG,
) -> list[dict[str, Any]]:
    """Evaluate candidate list with matched filter and update confirmation.

    Args:
        candidates: List of candidate dicts.
        code_config: Beacon code config.
        id_config: Identification thresholds and parameters.

    Returns:
        Sorted list of candidates (confirmed first, then highest score).
    """
    threshold = id_config.id_threshold
    confirm_frames = id_config.id_confirm_frames
    mode = code_config.mode

    for c in candidates:
        if mode == "steady":
            c["score"] = 1.0
            if c.get("total_observations", 0) >= confirm_frames:
                c["confirmed"] = True
            continue

        # Code mode
        res = compute_blink_score(c.get("history", []), code_config)
        score = res["score"]
        c["score"] = score

        if score >= threshold:
            c["confirm_streak"] = c.get("confirm_streak", 0) + 1
            if c["confirm_streak"] >= confirm_frames:
                c["confirmed"] = True
        else:
            c["confirm_streak"] = max(0, c.get("confirm_streak", 0) - 1)
            if c["confirm_streak"] == 0 and c.get("missed_frames", 0) > 5:
                c["confirmed"] = False

    # Sort
    def sort_key(c: dict[str, Any]) -> tuple[bool, float]:
        # Return tuple, Python sorts tuples element by element.
        # False < True, so we negate for descending order (True first)
        return (not c.get("confirmed", False), -c.get("score", 0.0))

    candidates.sort(key=sort_key)
    return candidates


def get_confirmed_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the confirmed candidate if any exists.

    Args:
        candidates: List of evaluated candidates.

    Returns:
        The confirmed candidate dict, or None.
    """
    if not candidates:
        return None
    for c in candidates:
        if c.get("confirmed"):
            return c
    return None
