"""Tests for BenchmarkPanel UI interactions, seed handling, cancellation, and report I/O."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from skylock.benchmark.catalog import builtin_scenarios
from skylock.benchmark.runner import RunRecord
from skylock.benchmark.scenario import Scenario
from skylock.ui.panels.benchmark import BenchmarkPanel

pytestmark = pytest.mark.gui


class FakeBenchmarkRunner:
    """Fast deterministic test runner returning synthetic RunRecords."""

    def __init__(self, delay_s: float = 0.0) -> None:
        self.delay_s = delay_s
        self.call_history: list[tuple[str, int]] = []

    def run(
        self,
        scenario: Scenario,
        seed: int,
        isolate: bool = False,
        output_dir: Any = None,
    ) -> RunRecord:
        self.call_history.append((scenario.id, seed))
        if self.delay_s > 0:
            time.sleep(self.delay_s)

        # Include measured metrics or None metrics based on scenario name
        is_none = "none" in scenario.id.lower()
        metrics: dict[str, Any] = {
            "acquisition_time_from_observable_s": {
                "status": "NOT_ACQUIRED" if is_none else "MEASURED",
                "value": None if is_none else 1.250,
                "reason": "Target never entered TRACK" if is_none else "",
            },
            "tracking_error_px": {
                "status": "NOT_RUN" if is_none else "MEASURED",
                "value": None if is_none else {"rms": 3.45, "mean": 2.50, "max": 6.10},
                "reason": "Requires ground truth" if is_none else "",
            },
            "target_loss_rate": {
                "status": "MEASURED",
                "value": 0.0200,
            },
            "reacquisition_time_s": {
                "status": "NOT_RUN" if is_none else "MEASURED",
                "value": None if is_none else {"mean_s": 0.350, "max_s": 0.400},
                "reason": "No loss event occurred" if is_none else "",
            },
            "fps_pipeline": {
                "status": "MEASURED",
                "value": 55.4,
            },
        }

        return RunRecord(
            run_id=f"run-{scenario.id}-{seed}",
            scenario_id=scenario.id,
            seed=seed,
            software_version="0.1.0",
            python_version="3.12.0",
            numpy_version="2.0.0",
            opencv_version="4.9.0",
            platform_info="TestPlatform",
            config_snapshot={
                "requirements": {
                    "acquisition_max_s": 2.0,
                    "tracking_error_px_max": 10.0,
                    "target_loss_rate_max": 0.05,
                    "reacquisition_max_s": 1.0,
                    "processing_fps_min": 20.0,
                }
            },
            config_hash="abc123hash",
            input_source=scenario.input_kind,
            duration_s=scenario.duration_s,
            frames=180,
            metrics=metrics,
            verdicts={
                "acquisition_time": "INDETERMINATE" if is_none else "PASS",
                "tracking_error": "INDETERMINATE" if is_none else "PASS",
                "target_loss_rate": "PASS",
                "reacquisition_time": "PASS",
                "processing_fps": "PASS",
                "overall": "INDETERMINATE" if is_none else "PASS",
            },
            overall_verdict="INDETERMINATE" if is_none else "PASS",
            started_at_utc="2026-10-01T12:00:00Z",
            wall_time_s=1.23,
            status="COMPLETED",
        )


def _wait_for_condition(cond, timeout_s: float = 3.0) -> bool:  # noqa: ANN001
    start = time.perf_counter()
    while (time.perf_counter() - start) < timeout_s:
        QCoreApplication.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_table_rows_colors_and_em_dash(qapp) -> None:
    """Assert table rows, formatting, colors, and None -> em dash with tooltip."""
    fake_runner = FakeBenchmarkRunner()
    panel = BenchmarkPanel(runner=fake_runner)  # type: ignore[arg-type]
    panel.show()

    # Create two scenarios: one with values, one with None
    sc1 = Scenario(id="S01_test", description="desc", duration_s=1.0)
    sc2 = Scenario(id="S02_none", description="desc", duration_s=1.0)

    panel._start_benchmark([sc1, sc2], [42])
    assert _wait_for_condition(lambda: len(panel._records) == 2)

    # Check row 0 (measured)
    for col in (0, 1, 2, 3, 4, 5, 6, 7):
        assert panel.table.item(0, col) is not None
    assert panel.table.item(0, 0).text() == "S01_test"  # type: ignore[union-attr]
    assert panel.table.item(0, 1).text() == "42"  # type: ignore[union-attr]
    assert panel.table.item(0, 2).text() == "PASS"  # type: ignore[union-attr]
    assert panel.table.item(0, 3).text() == "1.250"  # type: ignore[union-attr]
    assert panel.table.item(0, 4).text() == "3.45"  # type: ignore[union-attr]
    assert panel.table.item(0, 5).text() == "0.0200"  # type: ignore[union-attr]
    assert panel.table.item(0, 6).text() == "0.350"  # type: ignore[union-attr]
    assert panel.table.item(0, 7).text() == "55.4"  # type: ignore[union-attr]

    # Check row 1 (None metrics show em dash and tooltip)
    em_dash = "—"
    for col in (0, 2, 3, 4, 6):
        assert panel.table.item(1, col) is not None
    assert panel.table.item(1, 0).text() == "S02_none"  # type: ignore[union-attr]
    assert panel.table.item(1, 2).text() == "INDETERMINATE"  # type: ignore[union-attr]
    assert panel.table.item(1, 3).text() == em_dash  # type: ignore[union-attr]
    assert "Target never entered TRACK" in panel.table.item(1, 3).toolTip()  # type: ignore[union-attr]
    assert panel.table.item(1, 4).text() == em_dash  # type: ignore[union-attr]
    assert "Requires ground truth" in panel.table.item(1, 4).toolTip()  # type: ignore[union-attr]
    assert panel.table.item(1, 6).text() == em_dash  # type: ignore[union-attr]
    assert "No loss event occurred" in panel.table.item(1, 6).toolTip()  # type: ignore[union-attr]

    # Summary row updated
    assert "2 runs" in panel.lbl_summary.text()
    assert "PASS: 1" in panel.lbl_summary.text()
    assert "INDET: 1" in panel.lbl_summary.text()

    panel.close()


def test_seed_linking_and_parsing(qapp) -> None:
    """Test seed link checkbox, controls sync, and multi-seed comma parsing."""
    fake_runner = FakeBenchmarkRunner()
    panel = BenchmarkPanel(runner=fake_runner)  # type: ignore[arg-type]
    panel.show()

    # Link seed default is on -> spn_seed is read-only
    assert panel.chk_link_seed.isChecked() is True
    assert panel.spn_seed.isReadOnly() is True

    # Sync controls seed
    panel.sync_controls_seed(105)
    assert panel.spn_seed.value() == 105

    # Toggle off -> editable
    panel.chk_link_seed.setChecked(False)
    assert panel.spn_seed.isReadOnly() is False
    panel.spn_seed.setValue(200)

    # Multi-seeds parsing: valid comma separated
    panel.txt_seeds.setText("10, 20, 30")
    seeds = panel._parse_seeds()
    assert seeds is not None
    assert seeds == [10, 20, 30]

    sc = Scenario(id="S01_seed_test", description="desc")
    panel._start_benchmark([sc], seeds)
    assert _wait_for_condition(lambda: len(panel._records) == 3)
    assert [r.seed for r in panel._records] == [10, 20, 30]

    # Invalid seed string produces error and returns None (no execution)
    panel.txt_seeds.setText("1, x, 3")
    invalid_seeds = panel._parse_seeds()
    assert invalid_seeds is None
    assert "Invalid seed 'x'" in panel.lbl_status.text()

    panel.close()


def test_s16_skip_without_file(qapp) -> None:
    """When running S16 without an MP4 file selected, skip it with a descriptive message."""
    fake_runner = FakeBenchmarkRunner()
    panel = BenchmarkPanel(runner=fake_runner)  # type: ignore[arg-type]
    panel.show()

    s16 = next(s for s in builtin_scenarios() if s.id == "S16_mp4")
    panel._start_benchmark([s16], [42])

    assert len(panel._records) == 0
    assert "S16_mp4 skipped: no MP4 selected" in panel.lbl_status.text()

    # Now provide a file path and verify it runs
    panel._mp4_path = "mock/test.mp4"
    panel._start_benchmark([s16], [42])
    assert _wait_for_condition(lambda: len(panel._records) == 1)
    assert panel._records[0].scenario_id == "S16_mp4"

    panel.close()


def test_cancellation_and_shutdown(qapp) -> None:
    """Test cancel button stops remaining runs, and shutdown cleans up threads."""
    fake_runner = FakeBenchmarkRunner(delay_s=0.05)
    panel = BenchmarkPanel(runner=fake_runner)  # type: ignore[arg-type]
    panel.show()

    scenarios = [
        Scenario(id=f"S{i:02d}", description="") for i in range(1, 10)
    ]

    panel._start_benchmark(scenarios, [42])
    assert panel.btn_cancel.isEnabled() is True

    # Let the first task begin, then cancel
    time.sleep(0.06)
    panel._cancel_benchmark()
    assert "Cancelling" in panel.lbl_status.text()

    # Wait for worker to stop
    assert _wait_for_condition(lambda: panel._worker_thread is None, timeout_s=4.0)
    # Tasks run should be much less than total 9
    assert len(panel._records) < 9
    assert panel.btn_run.isEnabled() is True

    # Shutdown test while running
    panel._start_benchmark(scenarios, [42])
    panel.shutdown()
    assert panel._worker_thread is None
    assert panel._worker is None

    panel.close()


def test_export_and_load_report(qapp, tmp_path) -> None:
    """Test exporting JSON/Markdown and loading an existing report.json file."""
    fake_runner = FakeBenchmarkRunner()
    panel = BenchmarkPanel(runner=fake_runner)  # type: ignore[arg-type]
    panel.show()

    sc = Scenario(id="S01_export", description="")
    panel._start_benchmark([sc], [42])
    assert _wait_for_condition(lambda: len(panel._records) == 1)

    json_path = tmp_path / "test_report.json"
    md_path = tmp_path / "test_report.md"

    # Export JSON
    with open(json_path, "w", encoding="utf-8") as f:
        from skylock.benchmark.report import to_json_report, to_markdown_report
        f.write(to_json_report(panel._records))
    assert json_path.exists()
    assert "schema_version" in json_path.read_text(encoding="utf-8")

    # Export Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown_report(panel._records))
    assert md_path.exists()
    assert "# SkyLock Benchmark Report" in md_path.read_text(encoding="utf-8")

    # Load report back into panel
    fixture_path = Path("tests/fixtures/ui_report_seed42.json")
    load_target = fixture_path if fixture_path.exists() else json_path

    # Monkeypatch QFileDialog.getOpenFileName to return load_target
    from PySide6.QtWidgets import QFileDialog
    orig_get_open = QFileDialog.getOpenFileName
    QFileDialog.getOpenFileName = lambda *args, **kwargs: (str(load_target), "JSON (*.json)")  # type: ignore[assignment]
    try:
        panel._load_report()
        assert len(panel._records) >= 1
        assert panel.table.rowCount() == len(panel._records)
    finally:
        QFileDialog.getOpenFileName = orig_get_open  # type: ignore[assignment]

    panel.close()


@pytest.mark.slow
def test_e2e_s01_line_clean_seed42(qapp) -> None:
    """End-to-end benchmark comparison with actual BenchmarkRunner."""
    from skylock.benchmark.runner import BenchmarkRunner
    real_runner = BenchmarkRunner()
    panel = BenchmarkPanel(runner=real_runner)
    panel.show()

    s01 = next(s for s in builtin_scenarios() if s.id == "S01_line_clean")
    panel._start_benchmark([s01], [42])

    assert _wait_for_condition(lambda: len(panel._records) == 1, timeout_s=15.0)
    rec = panel._records[0]
    assert rec.overall_verdict == "PASS"
    assert rec.frames == 180
    assert rec.status == "COMPLETED"

    # Compare with a direct runner run
    direct_rec = real_runner.run(s01, seed=42)
    assert rec.overall_verdict == direct_rec.overall_verdict
    assert rec.frames == direct_rec.frames

    panel.close()
