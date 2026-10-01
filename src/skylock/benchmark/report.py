"""Benchmark report generation: JSON with schema versioning and Markdown summary."""

from __future__ import annotations

import json
import math
import statistics
from typing import Any

from skylock.benchmark.runner import RunRecord

_SCHEMA_VERSION = "1.0"


def to_json_report(records: list[RunRecord], indent: int = 2) -> str:
    """Serialize benchmark run records to JSON with schema version.

    Nulls are preserved (no zero-filling). Statistics are computed only over
    MEASURED values with sample size n shown.

    Args:
        records: List of RunRecord from benchmark execution.
        indent: JSON indentation level.

    Returns:
        JSON string with schema_version and runs array.
    """
    report: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "runs": [r.as_dict() for r in records],
        "summary": _build_summary(records),
    }
    return json.dumps(report, indent=indent, default=_json_default)


def _json_default(obj: Any) -> Any:
    """Handle non-serializable types in JSON output."""
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        if math.isinf(obj):
            return None
    return str(obj)


def to_markdown_report(records: list[RunRecord]) -> str:
    """Generate a human-readable Markdown summary table.

    Args:
        records: List of RunRecord from benchmark execution.

    Returns:
        Markdown string with scenario results table and verdict summary.
    """
    lines: list[str] = []
    lines.append("# SkyLock Benchmark Report\n")
    lines.append(f"Schema version: {_SCHEMA_VERSION}\n")
    lines.append(f"Total runs: {len(records)}\n")

    # Verdict summary
    verdict_counts: dict[str, int] = {}
    for r in records:
        v = r.overall_verdict
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    lines.append("\n## Verdict Summary\n")
    for v, c in sorted(verdict_counts.items()):
        lines.append(f"- **{v}**: {c}")
    lines.append("")

    # Per-scenario table
    lines.append("## Results\n")
    lines.append(
        "| Scenario | Seed | Verdict | Frames | Acq (s) | Err (px) | Loss Rate | FPS | Status |"
    )
    lines.append(
        "|----------|------|---------|--------|---------|----------|-----------|-----|--------|"
    )

    for r in records:
        acq_val = _extract_metric_value(r.metrics, "acquisition_time_from_observable_s")
        trk_val = _extract_metric_rms(r.metrics, "tracking_error_px")
        loss_val = _extract_metric_value(r.metrics, "target_loss_rate")
        fps_val = _extract_metric_value(r.metrics, "fps_pipeline")

        acq_str = f"{acq_val:.3f}" if acq_val is not None else "—"
        trk_str = f"{trk_val:.2f}" if trk_val is not None else "—"
        loss_str = f"{loss_val:.4f}" if loss_val is not None else "—"
        fps_str = f"{fps_val:.1f}" if fps_val is not None else "—"

        lines.append(
            f"| {r.scenario_id} | {r.seed} | {r.overall_verdict} | "
            f"{r.frames} | {acq_str} | {trk_str} | {loss_str} | {fps_str} | {r.status} |"
        )

    lines.append("")

    # Performance summary
    lines.append("## Performance Summary\n")

    fps_pipeline_values = [
        v for r in records
        if (v := _extract_metric_value(r.metrics, "fps_pipeline")) is not None
    ]
    fps_wall_values = [
        v for r in records
        if (v := _extract_metric_value(r.metrics, "fps_wall")) is not None
    ]
    latency_mean_values = [
        v.get("mean") for r in records
        if (entry := r.metrics.get("latency_ms", {}))
        and entry.get("status") == "MEASURED"
        and (v := entry.get("value"))
        and isinstance(v, dict)
    ]

    if fps_pipeline_values:
        fps_pipe_stats = _stats_over(fps_pipeline_values)
        lines.append(
            f"- **Pipeline FPS**: mean={fps_pipe_stats['mean']:.1f}, "
            f"min={fps_pipe_stats['min']:.1f}, max={fps_pipe_stats['max']:.1f} "
            f"(n={fps_pipe_stats['n']})"
        )

    if fps_wall_values:
        fps_wall_stats = _stats_over(fps_wall_values)
        lines.append(
            f"- **Wall-clock FPS**: mean={fps_wall_stats['mean']:.1f}, "
            f"min={fps_wall_stats['min']:.1f}, max={fps_wall_stats['max']:.1f} "
            f"(n={fps_wall_stats['n']})"
        )

    if latency_mean_values:
        lat_stats = _stats_over(latency_mean_values)
        lines.append(f"- **Mean Latency**: {lat_stats['mean']:.2f} ms (avg over runs)")

    lines.append("")

    # Aggregated statistics (only over MEASURED values)
    summary = _build_summary(records)
    if summary.get("aggregated"):
        lines.append("## Aggregated Tracking Metrics (MEASURED values only)\n")
        for key, stats in summary["aggregated"].items():
            n = stats.get("n", 0)
            if n > 0:
                mean = stats.get("mean")
                std = stats.get("std")
                mean_str = f"{mean:.4f}" if mean is not None else "—"
                std_str = f"{std:.4f}" if std is not None else "—"
                lines.append(f"- **{key}**: mean={mean_str}, std={std_str}, n={n}")
        lines.append("")

    return "\n".join(lines)


def _extract_metric_value(metrics: dict[str, Any], key: str) -> float | None:
    """Extract scalar metric value, returning None if not measured."""
    if not metrics:
        return None
    entry = metrics.get(key, {})
    if isinstance(entry, dict) and entry.get("status") == "MEASURED":
        return entry.get("value")
    return None


def _extract_metric_rms(metrics: dict[str, Any], key: str) -> float | None:
    """Extract RMS from ErrorStats metric value."""
    if not metrics:
        return None
    entry = metrics.get(key, {})
    if isinstance(entry, dict) and entry.get("status") == "MEASURED":
        val = entry.get("value")
        if isinstance(val, dict):
            return val.get("rms")
        return val
    return None


def _build_summary(records: list[RunRecord]) -> dict[str, Any]:
    """Build aggregated summary statistics over MEASURED values only."""
    # Group by scenario
    scenario_groups: dict[str, list[RunRecord]] = {}
    for r in records:
        scenario_groups.setdefault(r.scenario_id, []).append(r)

    # Aggregate key metrics
    aggregated: dict[str, dict[str, Any]] = {}

    # Acquisition time
    acq_values = [
        v for r in records
        if (v := _extract_metric_value(r.metrics, "acquisition_time_from_observable_s")) is not None
    ]
    aggregated["acquisition_time_s"] = _stats_over(acq_values)

    # Tracking error RMS
    trk_values = [
        v for r in records
        if (v := _extract_metric_rms(r.metrics, "tracking_error_px")) is not None
    ]
    aggregated["tracking_error_rms_px"] = _stats_over(trk_values)

    # Target loss rate
    loss_values = [
        v for r in records
        if (v := _extract_metric_value(r.metrics, "target_loss_rate")) is not None
    ]
    aggregated["target_loss_rate"] = _stats_over(loss_values)

    # Verdict counts
    verdict_counts: dict[str, int] = {}
    for r in records:
        v = r.overall_verdict
        verdict_counts[v] = verdict_counts.get(v, 0) + 1

    return {
        "total_runs": len(records),
        "verdict_counts": verdict_counts,
        "scenario_count": len(scenario_groups),
        "aggregated": aggregated,
    }


def _stats_over(values: list[float]) -> dict[str, Any]:
    """Compute statistics only over available MEASURED values."""
    n = len(values)
    if n == 0:
        return {"mean": None, "std": None, "min": None, "max": None, "n": 0}
    mean = statistics.mean(values)
    std = statistics.stdev(values) if n > 1 else 0.0
    return {
        "mean": mean,
        "std": std,
        "min": min(values),
        "max": max(values),
        "n": n,
    }


__all__ = ("to_json_report", "to_markdown_report")
