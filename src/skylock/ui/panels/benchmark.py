"""Benchmark execution panel for running scenario suites without freezing the UI."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from skylock.benchmark.catalog import builtin_scenarios
from skylock.benchmark.report import to_json_report, to_markdown_report
from skylock.benchmark.runner import BenchmarkRunner, RunRecord
from skylock.benchmark.scenario import Scenario
from skylock.config.models import SkyLockConfig


def _get_verdict_color(verdict: str) -> QColor:
    """Return background color corresponding to a verdict string."""
    if verdict == "PASS":
        return QColor("#065F46")
    if verdict == "FAIL":
        return QColor("#991B1B")
    if verdict == "INDETERMINATE":
        return QColor("#92400E")
    if verdict == "NOT_RUN":
        return QColor("#374151")
    return QColor("#1F2937")


class _BenchWorker(QObject):
    """Worker running benchmark scenarios sequentially off the main GUI thread."""

    record_ready = Signal(object)
    finished = Signal()

    def __init__(
        self,
        scenarios: list[Scenario],
        seeds: list[int],
        runner: BenchmarkRunner,
    ) -> None:
        super().__init__()
        self.scenarios = scenarios
        self.seeds = seeds
        self.runner = runner
        self._is_cancelled = False

    @Slot()
    def run(self) -> None:
        for sc in self.scenarios:
            for seed in self.seeds:
                if self._is_cancelled:
                    break
                try:
                    record = self.runner.run(sc, seed=seed)
                    self.record_ready.emit(record)
                except Exception as e:
                    # Emit a synthetic failed record on unexpected error
                    rec = RunRecord(
                        run_id="error",
                        scenario_id=sc.id,
                        seed=seed,
                        software_version="0.1.0",
                        python_version="",
                        numpy_version="",
                        opencv_version="",
                        platform_info="",
                        config_snapshot={},
                        config_hash="",
                        input_source=sc.input_kind,
                        duration_s=sc.duration_s,
                        frames=0,
                        metrics={},
                        verdicts={},
                        overall_verdict="FAIL",
                        started_at_utc="",
                        wall_time_s=0.0,
                        status="FAILED",
                        error=str(e),
                    )
                    self.record_ready.emit(rec)
        self.finished.emit()

    def cancel(self) -> None:
        self._is_cancelled = True


class BenchmarkPanel(QWidget):
    """Bottom tab / dock panel for running test scenarios and displaying results."""

    def __init__(
        self,
        runner: BenchmarkRunner | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.runner = runner if runner is not None else BenchmarkRunner(SkyLockConfig())
        self._records: list[RunRecord] = []
        self._worker_thread: QThread | None = None
        self._worker: _BenchWorker | None = None

        self._build_ui()
        self._populate_scenarios()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Controls bar
        ctrl_bar = QHBoxLayout()
        ctrl_bar.addWidget(QLabel("Scenario:"))
        self.cmb_scenarios = QComboBox()
        ctrl_bar.addWidget(self.cmb_scenarios)

        ctrl_bar.addWidget(QLabel("Seed:"))
        self.spn_seed = QSpinBox()
        self.spn_seed.setRange(0, 999999)
        self.spn_seed.setValue(42)
        ctrl_bar.addWidget(self.spn_seed)

        self.btn_run = QPushButton("Run Scenario")
        self.btn_run.clicked.connect(self._run_selected)
        ctrl_bar.addWidget(self.btn_run)

        self.btn_run_all = QPushButton("Run All")
        self.btn_run_all.clicked.connect(self._run_all)
        ctrl_bar.addWidget(self.btn_run_all)

        ctrl_bar.addStretch()

        self.btn_export_json = QPushButton("Export JSON")
        self.btn_export_json.clicked.connect(self._export_json)
        ctrl_bar.addWidget(self.btn_export_json)

        self.btn_export_md = QPushButton("Export Markdown")
        self.btn_export_md.clicked.connect(self._export_md)
        ctrl_bar.addWidget(self.btn_export_md)

        layout.addLayout(ctrl_bar)

        # Status label
        self.lbl_status = QLabel("Idle")
        self.lbl_status.setStyleSheet("color: #9CA3AF; font-style: italic;")
        layout.addWidget(self.lbl_status)

        # Table of results
        self.table = QTableWidget()
        cols = [
            "Scenario", "Seed", "Verdict", "Frames",
            "Time (s)", "Acq (s)", "Trk Err (px)",
            "Loss Rate", "Status",
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

    def _populate_scenarios(self) -> None:
        self.scenarios_list = list(builtin_scenarios())
        for sc in self.scenarios_list:
            self.cmb_scenarios.addItem(sc.id, sc)

    def _run_selected(self) -> None:
        sc = self.cmb_scenarios.currentData()
        if sc:
            self._start_benchmark([sc], [self.spn_seed.value()])

    def _run_all(self) -> None:
        self._start_benchmark(self.scenarios_list, [self.spn_seed.value()])

    def _start_benchmark(self, scenarios: list[Scenario], seeds: list[int]) -> None:
        if self._worker_thread is not None and self._worker_thread.isRunning():
            return

        self.btn_run.setEnabled(False)
        self.btn_run_all.setEnabled(False)
        self.lbl_status.setText(f"Running {len(scenarios)} scenario(s)...")

        self._worker_thread = QThread()
        self._worker = _BenchWorker(scenarios, seeds, self.runner)
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.record_ready.connect(self.add_record)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.start()

    def _on_finished(self) -> None:
        self.btn_run.setEnabled(True)
        self.btn_run_all.setEnabled(True)
        self.lbl_status.setText(f"Completed {len(self._records)} benchmark run(s)")

    @Slot(object)
    def add_record(self, record: RunRecord) -> None:
        """Add a RunRecord to the table with verdict color formatting."""
        self._records.append(record)
        row = self.table.rowCount()
        self.table.insertRow(row)

        acq = record.metrics.get("acquisition_time_from_observable_s", {})
        acq_val = acq.get("value") if isinstance(acq, dict) else None
        acq_str = f"{acq_val:.3f}" if acq_val is not None else "—"

        trk = record.metrics.get("tracking_error_px", {})
        trk_val = trk.get("value", {}) if isinstance(trk, dict) else {}
        trk_rms = trk_val.get("rms") if isinstance(trk_val, dict) else None
        trk_str = f"{trk_rms:.2f}" if trk_rms is not None else "—"

        loss = record.metrics.get("target_loss_rate", {})
        loss_val = loss.get("value") if isinstance(loss, dict) else None
        loss_str = f"{loss_val:.4f}" if loss_val is not None else "—"

        items = [
            record.scenario_id,
            str(record.seed),
            record.overall_verdict,
            str(record.frames),
            f"{record.wall_time_s:.2f}",
            acq_str,
            trk_str,
            loss_str,
            record.status,
        ]

        color = _get_verdict_color(record.overall_verdict)
        for col_idx, text in enumerate(items):
            item = QTableWidgetItem(text)
            if col_idx == 2:  # Verdict column
                item.setBackground(color)
                item.setForeground(QColor("#FFFFFF"))
            self.table.setItem(row, col_idx, item)

    def _export_json(self) -> None:
        if not self._records:
            QMessageBox.information(self, "Export", "No benchmark records to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save JSON Report", "report.json",
            "JSON (*.json)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_json_report(self._records))

    def _export_md(self) -> None:
        if not self._records:
            QMessageBox.information(self, "Export", "No benchmark records to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Markdown Report", "report.md",
            "Markdown (*.md)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_markdown_report(self._records))


__all__ = ("BenchmarkPanel",)
