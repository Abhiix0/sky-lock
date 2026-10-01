"""Deterministic comparison of benchmark run records.

Compares only deterministic fields (state timeline hash, estimates hash,
error stats, acquisition time) and ignores wall-clock fields (latency, fps,
timestamps, wall_time_s).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from skylock.benchmark.runner import RunRecord


@dataclass(frozen=True, slots=True)
class Diff:
    """Single field difference between two runs."""

    field: str
    value_a: Any
    value_b: Any
    reason: str


def compare_runs(
    a: RunRecord,
    b: RunRecord,
    tol: float = 1e-9,
) -> list[Diff]:
    """Compare two RunRecords on deterministic fields.

    Deterministic fields compared:
    - state_timeline_hash (exact)
    - estimates_hash (exact)
    - config_hash (exact)
    - frames count (exact)
    - scenario_id (exact)
    - seed (exact)
    - Error stats (within tol)
    - Acquisition time (within tol)

    Excluded (wall-clock dependent):
    - run_id, started_at_utc, wall_time_s
    - fps_pipeline, fps_wall, latency_ms

    Args:
        a: First RunRecord.
        b: Second RunRecord.
        tol: Numeric tolerance for floating-point comparisons.

    Returns:
        List of Diff objects. Empty list means deterministic equivalence.
    """
    diffs: list[Diff] = []

    # Exact match fields
    _exact(diffs, "scenario_id", a.scenario_id, b.scenario_id)
    _exact(diffs, "seed", a.seed, b.seed)
    _exact(diffs, "config_hash", a.config_hash, b.config_hash)
    _exact(diffs, "frames", a.frames, b.frames)
    _exact(diffs, "state_timeline_hash", a.state_timeline_hash, b.state_timeline_hash)
    _exact(diffs, "estimates_hash", a.estimates_hash, b.estimates_hash)
    _exact(diffs, "status", a.status, b.status)

    # Compare deterministic metrics (not wall-clock)
    _compare_metric_value(diffs, "acquisition_time_from_start_s", a.metrics, b.metrics, tol)
    _compare_metric_value(diffs, "acquisition_time_from_observable_s", a.metrics, b.metrics, tol)
    _compare_error_stats(diffs, "tracking_error_px", a.metrics, b.metrics, tol)
    _compare_error_stats(diffs, "pointing_error_px", a.metrics, b.metrics, tol)
    _compare_error_stats(diffs, "centering_error_px", a.metrics, b.metrics, tol)
    _compare_metric_value(diffs, "target_loss_rate", a.metrics, b.metrics, tol)
    _compare_metric_value(diffs, "lock_retention", a.metrics, b.metrics, tol)
    _compare_metric_value(diffs, "detection_rate", a.metrics, b.metrics, tol)

    # Compare verdicts
    _compare_verdicts(diffs, a.verdicts, b.verdicts)

    return diffs


def _exact(diffs: list[Diff], field: str, va: Any, vb: Any) -> None:
    """Compare exact match."""
    if va != vb:
        diffs.append(Diff(field=field, value_a=va, value_b=vb, reason="exact mismatch"))


def _close(a: float | None, b: float | None, tol: float) -> bool:
    """Check if two nullable floats are close within tolerance."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) <= tol


def _compare_metric_value(
    diffs: list[Diff],
    key: str,
    ma: dict[str, Any],
    mb: dict[str, Any],
    tol: float,
) -> None:
    """Compare scalar metric values within tolerance."""
    ea = ma.get(key, {}) if ma else {}
    eb = mb.get(key, {}) if mb else {}

    status_a = ea.get("status") if isinstance(ea, dict) else None
    status_b = eb.get("status") if isinstance(eb, dict) else None

    if status_a != status_b:
        diffs.append(
            Diff(
                field=f"{key}.status",
                value_a=status_a,
                value_b=status_b,
                reason="status mismatch",
            )
        )
        return

    val_a = ea.get("value") if isinstance(ea, dict) else None
    val_b = eb.get("value") if isinstance(eb, dict) else None

    if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
        if not _close(float(val_a), float(val_b), tol):
            diffs.append(
                Diff(
                    field=f"{key}.value",
                    value_a=val_a,
                    value_b=val_b,
                    reason=f"exceeds tol={tol}",
                )
            )
    elif val_a != val_b:
        diffs.append(
            Diff(field=f"{key}.value", value_a=val_a, value_b=val_b, reason="value mismatch")
        )


def _compare_error_stats(
    diffs: list[Diff],
    key: str,
    ma: dict[str, Any],
    mb: dict[str, Any],
    tol: float,
) -> None:
    """Compare ErrorStats sub-fields within tolerance."""
    ea = ma.get(key, {}) if ma else {}
    eb = mb.get(key, {}) if mb else {}

    status_a = ea.get("status") if isinstance(ea, dict) else None
    status_b = eb.get("status") if isinstance(eb, dict) else None

    if status_a != status_b:
        diffs.append(
            Diff(
                field=f"{key}.status",
                value_a=status_a,
                value_b=status_b,
                reason="status mismatch",
            )
        )
        return

    val_a = ea.get("value") if isinstance(ea, dict) else None
    val_b = eb.get("value") if isinstance(eb, dict) else None

    if isinstance(val_a, dict) and isinstance(val_b, dict):
        for stat_key in ("mean", "rms", "p95", "max", "n"):
            sa = val_a.get(stat_key)
            sb = val_b.get(stat_key)
            if stat_key == "n":
                if sa != sb:
                    diffs.append(Diff(
                        field=f"{key}.{stat_key}",
                        value_a=sa, value_b=sb,
                        reason="count mismatch",
                    ))
            elif (
                isinstance(sa, (int, float))
                and isinstance(sb, (int, float))
                and not _close(float(sa), float(sb), tol)
            ):
                diffs.append(Diff(
                    field=f"{key}.{stat_key}",
                    value_a=sa, value_b=sb,
                    reason=f"exceeds tol={tol}",
                ))
    elif val_a != val_b:
        diffs.append(
            Diff(field=f"{key}.value", value_a=val_a, value_b=val_b, reason="value mismatch")
        )


def _compare_verdicts(diffs: list[Diff], va: dict[str, str], vb: dict[str, str]) -> None:
    """Compare verdict dictionaries."""
    all_keys = set(va.keys()) | set(vb.keys())
    for k in sorted(all_keys):
        a_val = va.get(k)
        b_val = vb.get(k)
        if a_val != b_val:
            diffs.append(
                Diff(
                    field=f"verdicts.{k}",
                    value_a=a_val,
                    value_b=b_val,
                    reason="verdict mismatch",
                )
            )


__all__ = ("Diff", "compare_runs")
