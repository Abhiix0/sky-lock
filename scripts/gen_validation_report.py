"""Validation report generator.

Runs all built-in scenarios × seeds 1..5, writes JSON per run to runs/validation/,
then generates docs/VALIDATION_REPORT.md FROM THE JSON — no hand-typed numbers.

Usage:
    python scripts/gen_validation_report.py [--seeds 1,2,3,4,5] [--out runs/validation]
                                            [--report docs/VALIDATION_REPORT.md]
                                            [--scenarios S01,S02,...]

All numbers in the Markdown report are read from the JSON files.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure src/ is on the path when run directly
_repo_root = Path(__file__).parents[1]
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src"))

import skylock  # noqa: E402
from skylock.benchmark.catalog import builtin_scenarios  # noqa: E402
from skylock.benchmark.runner import BenchmarkRunner  # noqa: E402
from skylock.config.presets import spec_default  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(v: Any) -> str:
    """Format a value for Markdown table display."""
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "✓" if v else "✗"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def _verdict_badge(v: str | None) -> str:
    if v is None:
        return "—"
    v_up = v.upper()
    if v_up == "PASS":
        return "✅ PASS"
    if v_up == "FAIL":
        return "❌ FAIL"
    if v_up == "INDETERMINATE":
        return "⚠️ INDET"
    if v_up in ("NOT_RUN", "NOT RUN", "SKIPPED"):
        return "⏭ NOT_RUN"
    return v


def _metric_val(metrics: dict, key: str) -> str:
    """Extract a scalar metric value for display."""
    m = metrics.get(key, {})
    if not isinstance(m, dict):
        return "—"
    status = m.get("status", "not_run")
    val = m.get("value")
    if status != "measured" or val is None:
        return f"({status})"
    if isinstance(val, dict):
        # ErrorStats: show rms
        rms = val.get("rms")
        n = val.get("n", 0)
        if rms is not None:
            return f"{rms:.2f} px (n={n})"
        # ReacquisitionSummary: show max_s
        max_s = val.get("max_s")
        if max_s is not None:
            return f"{max_s:.3f} s"
    if isinstance(val, float):
        return f"{val:.3f}"
    if isinstance(val, bool):
        return "✓" if val else "✗"
    return str(val)


def _overall_from_record(record_dict: dict) -> str:
    """Extract overall verdict from a RunRecord dict."""
    verdicts = record_dict.get("verdicts", {})
    return verdicts.get("overall", "—")


def _collect_run_records(run_dir: Path) -> list[dict]:
    """Load all JSON run records from a directory."""
    records = []
    for f in sorted(run_dir.glob("*.json")):
        try:
            records.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  Warning: could not parse {f}: {e}")
    return records


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

_REQUIREMENT_KEYS = [
    ("acquisition_time", "Acq ≤ 2 s"),
    ("tracking_error", "Track ≤ 10 px"),
    ("target_loss_rate", "Loss < 5%"),
    ("reacquisition_time", "Reacq ≤ 1 s"),
    ("processing_fps", "FPS ≥ 20"),
]

_METRIC_DISPLAY_KEYS = [
    ("acquisition_time_from_start_s", "Acq time (start)"),
    ("acquisition_time_from_observable_s", "Acq time (obs)"),
    ("tracking_error_px", "Tracking error"),
    ("pointing_error_px", "Pointing error"),
    ("reacquisition_time_s", "Reacq time"),
    ("target_loss_rate", "Loss rate"),
    ("fps_pipeline", "Pipeline FPS"),
]


def _generate_markdown(records: list[dict], report_path: Path, run_dir: Path) -> None:
    """Generate VALIDATION_REPORT.md from loaded JSON records."""

    now = datetime.now(UTC).isoformat()

    lines: list[str] = [
        "# SkyLock Validation Report",
        "",
        f"> **Generated:** {now}  ",
        f"> **SkyLock version:** {skylock.__version__}  ",
        f"> **Source:** {run_dir.resolve()}  ",
        "> **Note:** All numbers are read directly from JSON run files — not hand-typed.",
        "",
        "---",
        "",
    ]

    if not records:
        lines += [
            "## No records found.",
            "",
            f"No JSON files found in `{run_dir}`. Run the script to generate results.",
            "",
        ]
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return

    # --- Aggregate counts ---
    all_overall: list[str] = []
    not_run_count = 0
    for rec in records:
        o = _overall_from_record(rec)
        if rec.get("status", "").lower() in ("not_run", "skipped"):
            not_run_count += 1
        else:
            all_overall.append(o.upper())

    pass_n = sum(1 for v in all_overall if v == "PASS")
    fail_n = sum(1 for v in all_overall if v == "FAIL")
    indet_n = sum(1 for v in all_overall if v == "INDETERMINATE")
    total = len(all_overall)

    lines += [
        "## Headline Verdict",
        "",
        "| Runs | PASS | FAIL | INDETERMINATE | NOT_RUN |",
        "|------|------|------|---------------|---------|",
        f"| {total} | {pass_n} | {fail_n} | {indet_n} | {not_run_count} |",
        "",
    ]

    # Overall verdict
    if fail_n > 0:
        headline = "❌ OVERALL: FAIL"
    elif indet_n > 0:
        headline = "⚠️ OVERALL: INDETERMINATE"
    elif pass_n == total and total > 0:
        headline = "✅ OVERALL: PASS"
    else:
        headline = "— OVERALL: NO RESULTS"

    lines += [f"**{headline}**", "", "---", ""]

    # --- Per-requirement summary table ---
    lines += [
        "## Per-Requirement Verdict Table",
        "",
        "Each cell shows the verdict for that scenario+seed run.",
        "",
    ]

    # Columns: scenario_id | seed | per-requirement verdicts...
    req_header = (
        "| Scenario | Seed | "
        + " | ".join(label for _, label in _REQUIREMENT_KEYS)
        + " | Overall |"
    )
    req_sep = "|" + "|".join(["-" * 12] * (len(_REQUIREMENT_KEYS) + 3)) + "|"
    lines += [req_header, req_sep]

    for rec in records:
        if rec.get("status", "").lower() in ("not_run", "skipped"):
            sid = rec.get("scenario_id", "—")
            seed = rec.get("seed", "—")
            lines.append(
                f"| {sid} | {seed} | "
                + " | ".join("⏭ NOT_RUN" for _ in _REQUIREMENT_KEYS)
                + " | ⏭ NOT_RUN |"
            )
            continue

        sid = rec.get("scenario_id", "—")
        seed = rec.get("seed", "—")
        verdicts = rec.get("verdicts", {})
        req_cells = " | ".join(
            _verdict_badge(verdicts.get(req_key)) for req_key, _ in _REQUIREMENT_KEYS
        )
        overall = _verdict_badge(verdicts.get("overall"))
        lines.append(f"| {sid} | {seed} | {req_cells} | {overall} |")

    lines += [""]

    # --- Per-metric detail table ---
    lines += [
        "## Per-Metric Detail",
        "",
        "Key measured values per run. `(status)` shown for non-MEASURED metrics.",
        "",
    ]

    metric_header = (
        "| Scenario | Seed | "
        + " | ".join(label for _, label in _METRIC_DISPLAY_KEYS)
        + " |"
    )
    metric_sep = "|" + "|".join(["-" * 18] * (len(_METRIC_DISPLAY_KEYS) + 2)) + "|"
    lines += [metric_header, metric_sep]

    for rec in records:
        if rec.get("status", "").lower() in ("not_run", "skipped"):
            sid = rec.get("scenario_id", "—")
            seed = rec.get("seed", "—")
            lines.append(
                f"| {sid} | {seed} | "
                + " | ".join("—" for _ in _METRIC_DISPLAY_KEYS)
                + " |"
            )
            continue

        sid = rec.get("scenario_id", "—")
        seed = rec.get("seed", "—")
        metrics = rec.get("metrics", {})
        metric_cells = " | ".join(
            _metric_val(metrics, mk) for mk, _ in _METRIC_DISPLAY_KEYS
        )
        lines.append(f"| {sid} | {seed} | {metric_cells} |")

    lines += [""]

    # --- Failures with root-cause notes ---
    failures = [
        rec for rec in records
        if rec.get("verdicts", {}).get("overall", "").upper() == "FAIL"
    ]
    if failures:
        lines += [
            "## Failures and Root-Cause Notes",
            "",
            "Scenarios that produced a FAIL verdict:",
            "",
        ]
        for rec in failures:
            sid = rec.get("scenario_id", "—")
            seed = rec.get("seed", "—")
            verdicts = rec.get("verdicts", {})
            failed_reqs = [k for k, v in verdicts.items() if v.upper() == "FAIL" and k != "overall"]
            lines += [
                f"### {sid} (seed={seed})",
                "",
                f"Failed requirements: `{'`, `'.join(failed_reqs)}`",
                "",
            ]
            # Per-failed-requirement: show the measured value vs threshold
            metrics = rec.get("metrics", {})
            for req_key, req_label in _REQUIREMENT_KEYS:
                if req_key in failed_reqs:
                    # Map requirement key to metric key
                    metric_map = {
                        "acquisition_time": "acquisition_time_from_observable_s",
                        "tracking_error": "tracking_error_px",
                        "target_loss_rate": "target_loss_rate",
                        "reacquisition_time": "reacquisition_time_s",
                        "processing_fps": "fps_pipeline",
                    }
                    mk = metric_map.get(req_key, req_key)
                    val = _metric_val(metrics, mk)
                    lines.append(f"- **{req_label}**: measured `{val}`")
            lines += ["", "> Root-cause: see scenario description and disturbance config.", ""]

    # --- INDETERMINATE entries ---
    indet_records = [
        rec for rec in records
        if rec.get("verdicts", {}).get("overall", "").upper() == "INDETERMINATE"
        and rec.get("status", "").lower() not in ("not_run", "skipped")
    ]
    if indet_records:
        lines += [
            "## Indeterminate Results",
            "",
            "These runs could not be fully evaluated (e.g. target never acquired, "
            "reacquisition never triggered):",
            "",
        ]
        for rec in indet_records:
            sid = rec.get("scenario_id", "—")
            seed = rec.get("seed", "—")
            verdicts = rec.get("verdicts", {})
            indet_reqs = [
                k for k, v in verdicts.items()
                if v.upper() == "INDETERMINATE" and k != "overall"
            ]
            lines.append(f"- **{sid}** (seed={seed}): `{'`, `'.join(indet_reqs)}`")
        lines += [""]

    # --- Provenance ---
    lines += [
        "## Provenance",
        "",
        f"- Report generated: `{now}`",
        f"- SkyLock version: `{skylock.__version__}`",
        f"- Total JSON run files: `{len(records)}`",
        f"- Scenarios with NOT_RUN status: `{not_run_count}`",
        "",
        "---",
        "*This report was generated by `scripts/gen_validation_report.py`. "
        "Do not hand-edit numbers.*",
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written to: {report_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SkyLock validation report")
    parser.add_argument("--seeds", type=str, default="1,2,3,4,5", help="Comma-separated seeds")
    parser.add_argument(
        "--out", type=str, default="runs/validation",
        help="Output directory for JSON",
    )
    parser.add_argument(
        "--report",
        type=str,
        default="docs/VALIDATION_REPORT.md",
        help="Output Markdown report path",
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        default="",
        help="Comma-separated scenario IDs (default: all built-in except S16_mp4)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=6.0,
        help="Simulation duration per run in seconds (default: 6.0)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip scenarios whose JSON already exists in --out",
    )
    args = parser.parse_args()

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = Path(args.report)

    all_scenarios = {s.id: s for s in builtin_scenarios()}
    if args.scenarios:
        scenario_ids = [s.strip() for s in args.scenarios.split(",") if s.strip()]
        scenarios = [all_scenarios[sid] for sid in scenario_ids if sid in all_scenarios]
    else:
        # Skip S16_mp4 (requires external file) and process everything else
        scenarios = [s for s in all_scenarios.values() if s.id != "S16_mp4"]

    print("SkyLock Validation Report Generator")
    print(f"  Scenarios : {len(scenarios)}")
    print(f"  Seeds     : {seeds}")
    print(f"  Duration  : {args.duration:.1f} s per run")
    print(f"  Output    : {out_dir}")
    print()

    base_cfg = spec_default()
    runner = BenchmarkRunner(base_cfg)

    total_runs = len(scenarios) * len(seeds)
    completed = 0
    existing_files: list[Path] = []

    for scenario in scenarios:
        for seed in seeds:
            run_key = f"{scenario.id}_seed{seed}"
            out_file = out_dir / f"{run_key}.json"

            if args.skip_existing and out_file.exists():
                print(f"  [{completed + 1}/{total_runs}] SKIP {run_key} (exists)")
                existing_files.append(out_file)
                completed += 1
                continue

            print(f"  [{completed + 1}/{total_runs}] Running {run_key} ...", end=" ", flush=True)

            # Apply duration override (do not mutate the scenario dataclass)
            from dataclasses import replace as dc_replace
            scenario_run = dc_replace(scenario, duration_s=args.duration)

            try:
                record = runner.run(scenario_run, seed)
                record_dict = record.as_dict()
                out_file.write_text(json.dumps(record_dict, indent=2), encoding="utf-8")
                overall = record_dict.get("verdicts", {}).get("overall", "—")
                print(f"overall={overall}  frames={record.frames}")
            except Exception as e:
                print(f"ERROR: {e}")
                # Write a failed record so the report captures the error
                error_record = {
                    "run_id": str(uuid.uuid4()),
                    "scenario_id": scenario.id,
                    "seed": seed,
                    "status": "error",
                    "error": str(e),
                    "verdicts": {"overall": "FAIL"},
                    "metrics": {},
                    "frames": 0,
                }
                out_file.write_text(json.dumps(error_record, indent=2), encoding="utf-8")

            completed += 1

    print()
    print("Loading results and generating Markdown report...")

    all_records = _collect_run_records(out_dir)
    _generate_markdown(all_records, report_path, out_dir)

    # Print headline
    pass_n = sum(
        1 for r in all_records
        if r.get("verdicts", {}).get("overall", "").upper() == "PASS"
    )
    fail_n = sum(
        1 for r in all_records
        if r.get("verdicts", {}).get("overall", "").upper() == "FAIL"
    )
    indet_n = sum(
        1 for r in all_records
        if r.get("verdicts", {}).get("overall", "").upper() == "INDETERMINATE"
    )
    not_run_n = sum(
        1 for r in all_records
        if r.get("status", "").lower() in ("not_run", "skipped")
    )
    print()
    print(f"Results: {pass_n} PASS / {fail_n} FAIL / {indet_n} INDETERMINATE / {not_run_n} NOT_RUN")


if __name__ == "__main__":
    main()
