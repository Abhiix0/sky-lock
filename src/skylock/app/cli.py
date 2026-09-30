"""SkyLock command-line interface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

import skylock


def build_parser() -> argparse.ArgumentParser:
    """Build the root argument parser for the skylock CLI."""
    parser = argparse.ArgumentParser(
        prog="skylock",
        description="SkyLock electro-optical tracking system",
    )
    parser.add_argument(
        "--version", action="version", version=f"skylock {skylock.__version__}"
    )

    sub = parser.add_subparsers(dest="command")

    # bench subcommand
    bench = sub.add_parser("bench", help="Run deterministic benchmarks")
    bench.add_argument(
        "--scenarios",
        type=str,
        default=None,
        help="Comma-separated scenario IDs (e.g. S01_line_clean,S05_line_spec_noise)",
    )
    bench.add_argument(
        "--all",
        action="store_true",
        dest="all_scenarios",
        help="Run all built-in scenarios",
    )
    bench.add_argument(
        "--seeds",
        type=str,
        default="42",
        help="Comma-separated seed values (e.g. 1,2,3)",
    )
    bench.add_argument(
        "--out",
        type=str,
        default="runs/benchmark",
        help="Output directory for results",
    )
    bench.add_argument(
        "--isolate",
        action="store_true",
        help="Run each scenario in a spawned subprocess for isolation",
    )
    bench.add_argument(
        "--fail-on-verdict",
        action="store_true",
        dest="fail_on_verdict",
        help="Exit non-zero if any scenario verdict is FAIL",
    )
    bench.add_argument(
        "--mp4",
        type=str,
        default=None,
        help="Path to MP4 file for S16_mp4 scenario",
    )

    return parser


def cli_main(argv: Sequence[str] | None = None) -> int:
    """Execute the CLI, returning an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "bench":
        return _run_bench(args)

    parser.print_help()
    return 0


def _run_bench(args: argparse.Namespace) -> int:
    """Execute the benchmark subcommand."""
    from skylock.benchmark.catalog import builtin_scenarios
    from skylock.benchmark.report import to_json_report, to_markdown_report
    from skylock.benchmark.runner import BenchmarkRunner, RunRecord
    from skylock.config.models import SkyLockConfig

    # Parse seeds
    try:
        seeds = [int(s.strip()) for s in args.seeds.split(",")]
    except ValueError:
        print("Error: --seeds must be comma-separated integers", file=sys.stderr)
        return 1

    # Resolve scenarios
    all_scenarios = {s.id: s for s in builtin_scenarios()}

    if args.all_scenarios:
        selected = list(all_scenarios.values())
    elif args.scenarios:
        ids = [s.strip() for s in args.scenarios.split(",")]
        selected = []
        for sid in ids:
            if sid not in all_scenarios:
                print(f"Error: unknown scenario '{sid}'", file=sys.stderr)
                print(f"Available: {', '.join(sorted(all_scenarios.keys()))}", file=sys.stderr)
                return 1
            selected.append(all_scenarios[sid])
    else:
        print("Error: specify --scenarios or --all", file=sys.stderr)
        return 1

    # Apply MP4 path if provided
    if args.mp4:
        from skylock.benchmark.scenario import Scenario

        mp4_path = str(Path(args.mp4).resolve())
        updated = []
        for s in selected:
            if s.id == "S16_mp4":
                updated.append(Scenario(
                    id=s.id,
                    description=s.description,
                    overrides=s.overrides,
                    duration_s=s.duration_s,
                    seeds=s.seeds,
                    input_kind="mp4",
                    mp4_path=mp4_path,
                    tags=s.tags,
                ))
            else:
                updated.append(s)
        selected = updated

    # Create output directory
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    runner = BenchmarkRunner(base_config=SkyLockConfig())
    records: list[RunRecord] = []

    total = len(selected) * len(seeds)
    count = 0

    for scenario in selected:
        for seed in seeds:
            count += 1
            print(f"[{count}/{total}] Running {scenario.id} seed={seed}...", flush=True)
            try:
                record = runner.run(scenario, seed, isolate=args.isolate)
                records.append(record)
                print(
                    f"  -> {record.overall_verdict} "
                    f"({record.frames} frames, {record.wall_time_s:.2f}s)"
                )
            except Exception as e:
                print(f"  -> HARNESS ERROR: {e}", file=sys.stderr)
                return 2

    # Write reports
    json_path = out_dir / "report.json"
    json_path.write_text(to_json_report(records), encoding="utf-8")
    print(f"\nJSON report: {json_path}")

    md_path = out_dir / "report.md"
    md_path.write_text(to_markdown_report(records), encoding="utf-8")
    print(f"Markdown report: {md_path}")

    # Summary
    verdicts = [r.overall_verdict for r in records]
    n_pass = verdicts.count("PASS")
    n_fail = verdicts.count("FAIL")
    n_indet = verdicts.count("INDETERMINATE")
    n_not_run = verdicts.count("NOT_RUN")
    print(f"\nSummary: {n_pass} PASS, {n_fail} FAIL, {n_indet} INDETERMINATE, {n_not_run} NOT_RUN")

    if args.fail_on_verdict and n_fail > 0:
        return 1

    return 0


__all__ = ("build_parser", "cli_main")
