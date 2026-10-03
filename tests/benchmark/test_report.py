"""Report tests: JSON nulls preserved, aggregation only over MEASURED values with n shown."""

from __future__ import annotations

import json

import pytest

from skylock.benchmark.catalog import builtin_scenarios
from skylock.benchmark.report import to_json_report, to_markdown_report
from skylock.benchmark.runner import BenchmarkRunner, RunRecord
from skylock.config.models import SkyLockConfig


@pytest.fixture()
def runner() -> BenchmarkRunner:
    return BenchmarkRunner(base_config=SkyLockConfig())


@pytest.fixture()
def sample_records(runner: BenchmarkRunner) -> list[RunRecord]:
    scenarios = {s.id: s for s in builtin_scenarios()}
    records = [
        runner.run(scenarios["S01_line_clean"], seed=42),
        runner.run(scenarios["S05_line_spec_noise"], seed=42),
    ]
    return records


def test_json_report_schema_version(sample_records: list[RunRecord]) -> None:
    """JSON report must contain schema_version."""
    report_str = to_json_report(sample_records)
    report = json.loads(report_str)

    assert "schema_version" in report
    assert report["schema_version"] == "1.0"
    assert "runs" in report
    assert len(report["runs"]) == 2


def test_json_report_nulls_preserved(sample_records: list[RunRecord]) -> None:
    """Nulls in metrics must be preserved, not replaced with zeros."""
    report_str = to_json_report(sample_records)

    # Parse and look for metrics with null values
    report = json.loads(report_str)
    for run in report["runs"]:
        metrics = run.get("metrics", {})
        for key, metric_entry in metrics.items():
            if isinstance(metric_entry, dict):
                status = metric_entry.get("status")
                value = metric_entry.get("value")
                if status != "MEASURED":
                    assert value is None, (
                        f"Non-MEASURED metric '{key}' has non-null value: {value}"
                    )


def test_json_report_aggregation_n(sample_records: list[RunRecord]) -> None:
    """Aggregated statistics must show n (count of MEASURED values)."""
    report_str = to_json_report(sample_records)
    report = json.loads(report_str)

    summary = report.get("summary", {})
    aggregated = summary.get("aggregated", {})

    for key, stats in aggregated.items():
        assert "n" in stats, f"Aggregated stat '{key}' missing 'n'"
        n = stats["n"]
        assert isinstance(n, int), f"n must be int, got {type(n)}"


def test_markdown_report_structure(sample_records: list[RunRecord]) -> None:
    """Markdown report must contain header, verdict summary, and results table."""
    md = to_markdown_report(sample_records)

    assert "# SkyLock Benchmark Report" in md
    assert "## Verdict Summary" in md
    assert "## Results" in md
    assert "| Scenario |" in md


def test_not_run_in_report(runner: BenchmarkRunner) -> None:
    """NOT_RUN records must appear in the report, not be omitted."""
    s16 = next(s for s in builtin_scenarios() if s.id == "S16_mp4")
    record = runner.run(s16, seed=1)

    report_str = to_json_report([record])
    report = json.loads(report_str)

    assert len(report["runs"]) == 1
    assert report["runs"][0]["status"] == "NOT_RUN"
    assert report["runs"][0]["overall_verdict"] == "NOT_RUN"

    md = to_markdown_report([record])
    assert "NOT_RUN" in md
