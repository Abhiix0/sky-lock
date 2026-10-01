"""Detailed inspection dialog for an individual benchmark run record."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from skylock.benchmark.runner import RunRecord

_EM_DASH = "—"


def _verdict_color(v: str) -> QColor:
    if v == "PASS":
        return QColor("#065F46")
    if v == "FAIL":
        return QColor("#991B1B")
    if v == "INDETERMINATE":
        return QColor("#92400E")
    if v == "NOT_RUN":
        return QColor("#374151")
    return QColor("#1F2937")


class BenchmarkDetailDialog(QDialog):
    """Detailed view for a single benchmark RunRecord."""

    def __init__(self, record: RunRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.record = record
        self.setWindowTitle(f"Run Details — {record.scenario_id} (Seed {record.seed})")
        self.resize(750, 600)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Header Provenance Form
        meta_box = QGroupBox("Run Provenance & Environment")
        m_layout = QFormLayout(meta_box)
        m_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Hash, software, platform, started_at
        lbl_hash = QLabel(self.record.config_hash or _EM_DASH)
        lbl_versions = QLabel(
            f"Software: {self.record.software_version} | "
            f"Python: {self.record.python_version} | "
            f"NumPy: {self.record.numpy_version} | "
            f"OpenCV: {self.record.opencv_version}"
        )
        lbl_platform = QLabel(self.record.platform_info or _EM_DASH)
        lbl_started = QLabel(self.record.started_at_utc or _EM_DASH)
        lbl_wall = QLabel(f"{self.record.wall_time_s:.3f} s ({self.record.frames} frames)")

        mono = "font-family: 'Consolas', 'Courier New', monospace; font-size: 11px;"
        for lbl in (lbl_hash, lbl_versions, lbl_platform, lbl_started, lbl_wall):
            lbl.setStyleSheet(mono)

        m_layout.addRow("Config Hash:", lbl_hash)
        m_layout.addRow("Versions:", lbl_versions)
        m_layout.addRow("Platform:", lbl_platform)
        m_layout.addRow("Started UTC:", lbl_started)
        m_layout.addRow("Execution:", lbl_wall)
        layout.addWidget(meta_box)

        # 2. Per-Requirement Evaluation Table
        req_box = QGroupBox("Requirement Evaluation")
        r_layout = QVBoxLayout(req_box)

        self.table = QTableWidget()
        cols = ["Requirement", "Measured Value", "Threshold", "Verdict", "Status / Reason"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self._populate_requirements_table()
        r_layout.addWidget(self.table)
        layout.addWidget(req_box)

        # 3. Error Box (if any)
        if self.record.error:
            err_box = QGroupBox("Error Information")
            e_layout = QVBoxLayout(err_box)
            err_text = QTextEdit()
            err_text.setReadOnly(True)
            err_text.setPlainText(self.record.error)
            err_text.setMaximumHeight(80)
            e_layout.addWidget(err_text)
            layout.addWidget(err_box)

        # 4. Action buttons
        btn_bar = QHBoxLayout()
        self.btn_copy_json = QPushButton("Copy JSON")
        self.btn_copy_json.clicked.connect(self._copy_json)
        btn_bar.addWidget(self.btn_copy_json)

        btn_bar.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(self.btn_close)

        layout.addLayout(btn_bar)

    def _populate_requirements_table(self) -> None:
        req_snapshot = (
            self.record.config_snapshot.get("requirements", {})
            if isinstance(self.record.config_snapshot, dict)
            else {}
        )

        # Canonical requirement keys mapped to evaluation
        req_specs: list[tuple[str, str, str, str]] = [
            (
                "Acquisition Time",
                "acquisition_time",
                "acquisition_time_from_observable_s",
                f"<= {req_snapshot.get('acquisition_max_s', 2.0):.1f} s"
                if "acquisition_max_s" in req_snapshot
                else _EM_DASH,
            ),
            (
                "Tracking Error",
                "tracking_error",
                "tracking_error_px",
                f"<= {req_snapshot.get('tracking_error_px_max', 10.0):.1f} px"
                if "tracking_error_px_max" in req_snapshot
                else _EM_DASH,
            ),
            (
                "Target Loss Rate",
                "target_loss_rate",
                "target_loss_rate",
                f"<= {req_snapshot.get('target_loss_rate_max', 0.05) * 100:.1f}%"
                if "target_loss_rate_max" in req_snapshot
                else _EM_DASH,
            ),
            (
                "Reacquisition Time",
                "reacquisition_time",
                "reacquisition_time_s",
                f"<= {req_snapshot.get('reacquisition_max_s', 1.0):.1f} s"
                if "reacquisition_max_s" in req_snapshot
                else _EM_DASH,
            ),
            (
                "Processing Cadence",
                "processing_fps",
                "fps_pipeline",
                f">= {req_snapshot.get('processing_fps_min', 20.0):.1f} FPS"
                if "processing_fps_min" in req_snapshot
                else _EM_DASH,
            ),
        ]

        self.table.setRowCount(len(req_specs))

        for row, (display_name, verdict_key, metric_key, threshold_str) in enumerate(req_specs):
            verdict = self.record.verdicts.get(verdict_key, _EM_DASH)
            metric_entry = self.record.metrics.get(metric_key, {})

            measured_str = _EM_DASH
            status_reason = _EM_DASH

            if isinstance(metric_entry, dict):
                st = metric_entry.get("status", "")
                reason = metric_entry.get("reason", "")
                val = metric_entry.get("value")

                if st == "MEASURED" and val is not None:
                    if isinstance(val, dict):
                        # e.g. ErrorStats (rms, mean, max) or ReacqStats (max_s, mean_s)
                        if "rms" in val:
                            measured_str = f"RMS: {val['rms']:.2f} px"
                        elif "max_s" in val:
                            measured_str = f"Max: {val['max_s']:.3f} s"
                        else:
                            measured_str = str(val)
                    elif isinstance(val, float):
                        if "fps" in metric_key:
                            measured_str = f"{val:.1f} FPS"
                        elif "loss" in metric_key:
                            measured_str = f"{val * 100:.2f}%"
                        else:
                            measured_str = f"{val:.3f} s"
                    else:
                        measured_str = str(val)
                    status_reason = "MEASURED"
                else:
                    status_reason = f"{st}: {reason}" if reason else st

            items = [
                display_name,
                measured_str,
                threshold_str,
                verdict,
                status_reason,
            ]

            v_color = _verdict_color(verdict)
            for col_idx, text in enumerate(items):
                item = QTableWidgetItem(text)
                if col_idx == 3:  # Verdict column
                    item.setBackground(v_color)
                    item.setForeground(QColor("#FFFFFF"))
                    item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col_idx, item)

    def _copy_json(self) -> None:
        """Copy the full run record serialized dictionary to system clipboard."""
        raw_dict = self.record.as_dict()
        json_str = json.dumps(raw_dict, indent=2)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(json_str)
            self.btn_copy_json.setText("Copied!")


__all__ = ("BenchmarkDetailDialog",)
