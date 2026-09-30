"""Configuration and runtime control panel for the SkyLock tracking interface."""

from __future__ import annotations

import random
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from skylock.config.models import SkyLockConfig
from skylock.core.enums import ControlMode, InputKind
from skylock.ui.config_editor import ConfigEditor


class ControlsPanel(QWidget):
    """Left dock control panel providing interactive system configuration."""

    config_changed = Signal(object)  # Emits SkyLockConfig
    start_clicked = Signal()
    stop_clicked = Signal()
    reset_clicked = Signal()
    manual_rate_changed = Signal(float, float)

    def __init__(self, initial_config: SkyLockConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = ConfigEditor(initial_config)
        self._block_signals = False
        self._build_ui()
        self._sync_widgets_from_config(self.editor.config)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)

        # 1. Execution controls (Start / Stop / Reset)
        run_box = QGroupBox("Run Control")
        r_layout = QHBoxLayout(run_box)
        self.btn_start = QPushButton("Start")
        self.btn_start.setStyleSheet("background-color: #065F46; color: white; font-weight: bold;")
        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setStyleSheet("background-color: #991B1B; color: white; font-weight: bold;")
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self.reset_clicked.emit)
        r_layout.addWidget(self.btn_start)
        r_layout.addWidget(self.btn_stop)
        r_layout.addWidget(self.btn_reset)
        layout.addWidget(run_box)

        # Inline Error Display
        self.lbl_error = QLabel()
        self.lbl_error.setWordWrap(True)
        self.lbl_error.setStyleSheet("color: #EF4444; font-weight: bold; padding: 4px;")
        self.lbl_error.hide()
        layout.addWidget(self.lbl_error)

        # 2. Input Source
        input_box = QGroupBox("Input Source")
        i_layout = QFormLayout(input_box)
        self.cmb_input = QComboBox()
        self.cmb_input.addItems(["Simulation", "MP4 Video"])
        self.cmb_input.currentIndexChanged.connect(self._on_input_changed)
        self.btn_browse_mp4 = QPushButton("Browse MP4...")
        self.btn_browse_mp4.clicked.connect(self._browse_mp4)
        self.btn_browse_mp4.hide()
        self.lbl_mp4_path = QLabel("No file selected")
        self.lbl_mp4_path.hide()
        i_layout.addRow("Source:", self.cmb_input)
        i_layout.addRow(self.btn_browse_mp4)
        i_layout.addRow(self.lbl_mp4_path)
        layout.addWidget(input_box)

        # 3. Control Mode & Manual Steering
        mode_box = QGroupBox("Gimbal Control Mode")
        m_layout = QFormLayout(mode_box)
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["AUTO", "MANUAL"])
        self.cmb_mode.currentIndexChanged.connect(self._on_mode_changed)
        m_layout.addRow("Mode:", self.cmb_mode)
        layout.addWidget(mode_box)

        # 4. Camera & Gimbal
        cam_box = QGroupBox("Camera & Gimbal")
        c_layout = QFormLayout(cam_box)
        self.spn_fps = QDoubleSpinBox()
        self.spn_fps.setRange(1.0, 120.0)
        self.spn_fps.setValue(30.0)
        self.spn_fps.valueChanged.connect(self._on_param_changed)

        self.spn_slew = QDoubleSpinBox()
        self.spn_slew.setRange(0.1, 50.0)  # Allow testing invalid values like 11
        self.spn_slew.setValue(5.0)
        self.spn_slew.valueChanged.connect(self._on_param_changed)

        c_layout.addRow("Camera FPS:", self.spn_fps)
        c_layout.addRow("Max Slew (°/s):", self.spn_slew)
        layout.addWidget(cam_box)

        # 5. Target Controls
        tgt_box = QGroupBox("Target Settings")
        t_layout = QFormLayout(tgt_box)
        self.cmb_tgt_motion = QComboBox()
        self.cmb_tgt_motion.addItems(["line", "circle", "figure8", "random"])
        self.cmb_tgt_motion.currentIndexChanged.connect(self._on_target_changed)
        self.spn_tgt_size = QSpinBox()
        self.spn_tgt_size.setRange(5, 20)
        self.spn_tgt_size.setValue(10)
        self.spn_tgt_size.valueChanged.connect(self._on_target_changed)
        self.cmb_tgt_shape = QComboBox()
        self.cmb_tgt_shape.addItems(["disc", "gaussian", "rect"])
        self.cmb_tgt_shape.currentIndexChanged.connect(self._on_target_changed)
        self.chk_rand_pos = QCheckBox("Random Initial Position")
        self.chk_rand_pos.toggled.connect(self._on_target_changed)
        t_layout.addRow("Motion:", self.cmb_tgt_motion)
        t_layout.addRow("Size (px):", self.spn_tgt_size)
        t_layout.addRow("Shape:", self.cmb_tgt_shape)
        t_layout.addRow(self.chk_rand_pos)
        layout.addWidget(tgt_box)

        # 6. Disturbances
        dist_box = QGroupBox("Disturbances")
        d_layout = QFormLayout(dist_box)
        self.chk_gauss = QCheckBox("Gaussian Noise (σ=20)")
        self.chk_sp = QCheckBox("Salt & Pepper (0.01)")
        self.chk_poisson = QCheckBox("Poisson Photon Noise")
        self.chk_jitter = QCheckBox("Platform Jitter (50 Hz)")
        self.chk_drift = QCheckBox("Platform Drift")
        self.chk_blur = QCheckBox("Optical Blur (σ=2)")
        self.cmb_atmos = QComboBox()
        self.cmb_atmos.addItems(["Clear", "Haze", "Fog", "Rain"])

        checkboxes = (
            self.chk_gauss, self.chk_sp, self.chk_poisson,
            self.chk_jitter, self.chk_drift, self.chk_blur,
        )
        for chk in checkboxes:
            chk.toggled.connect(self._on_dist_changed)
            d_layout.addRow(chk)
        self.cmb_atmos.currentIndexChanged.connect(self._on_dist_changed)
        d_layout.addRow("Atmosphere:", self.cmb_atmos)
        layout.addWidget(dist_box)

        # 7. Seed Control
        seed_box = QGroupBox("RNG Seed")
        s_layout = QHBoxLayout(seed_box)
        self.spn_seed = QSpinBox()
        self.spn_seed.setRange(0, 999999)
        self.spn_seed.setValue(42)
        self.spn_seed.valueChanged.connect(self._on_seed_changed)
        self.btn_random_seed = QPushButton("Randomise")
        self.btn_random_seed.clicked.connect(self._randomise_seed)
        s_layout.addWidget(self.spn_seed)
        s_layout.addWidget(self.btn_random_seed)
        layout.addWidget(seed_box)

        layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _sync_widgets_from_config(self, cfg: SkyLockConfig) -> None:
        self._block_signals = True
        try:
            self.spn_fps.setValue(cfg.camera.fps)
            self.spn_slew.setValue(cfg.gimbal.slew_rate_deg_s)
            self.spn_seed.setValue(cfg.seed)
            if cfg.target.targets:
                t0 = cfg.target.targets[0]
                self.spn_tgt_size.setValue(t0.size_px)
                idx = self.cmb_tgt_shape.findText(t0.shape)
                if idx >= 0:
                    self.cmb_tgt_shape.setCurrentIndex(idx)
        finally:
            self._block_signals = False

    def _on_start(self) -> None:
        """Handle Start button: only starts if configuration is valid."""
        if self.lbl_error.isVisible():
            return
        self.start_clicked.emit()

    def _on_input_changed(self) -> None:
        is_mp4 = self.cmb_input.currentText() == "MP4 Video"
        self.btn_browse_mp4.setVisible(is_mp4)
        self.lbl_mp4_path.setVisible(is_mp4)
        kind = InputKind.MP4.value if is_mp4 else InputKind.SIMULATION.value
        self._apply_dict({"input.kind": kind})

    def _browse_mp4(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Video", "", "Video Files (*.mp4 *.avi)")
        if path:
            self.lbl_mp4_path.setText(path)
            self._apply_dict({"input.mp4_path": path})

    def _on_mode_changed(self) -> None:
        is_manual = self.cmb_mode.currentText() == "MANUAL"
        mode = ControlMode.MANUAL.value if is_manual else ControlMode.AUTO.value
        self._apply_dict({"control.mode": mode})

    def _on_param_changed(self) -> None:
        if self._block_signals:
            return
        self._apply_dict({
            "camera.fps": self.spn_fps.value(),
            "gimbal.slew_rate_deg_s": self.spn_slew.value(),
        })

    def _on_target_changed(self) -> None:
        if self._block_signals:
            return
        m_kind = self.cmb_tgt_motion.currentText()
        motion_dict: dict[str, Any] = {"kind": m_kind}
        if m_kind == "line":
            motion_dict.update({"speed_deg_s": 0.5, "heading_deg": 0.0})
        elif m_kind == "circle":
            motion_dict.update({"radius_deg": 0.8, "period_s": 8.0, "phase_rad": 0.0})
        elif m_kind == "figure8":
            motion_dict.update({"extent_deg": 1.0, "period_s": 8.0})

        init_mode = "random" if self.chk_rand_pos.isChecked() else "fixed"
        self._apply_dict({
            "target.targets": [{
                "id": "target_0",
                "size_px": self.spn_tgt_size.value(),
                "shape": self.cmb_tgt_shape.currentText(),
                "brightness": 220.0,
                "initial": init_mode,
                "initial_pos_deg": [2.0, 1.0],
                "motion": motion_dict,
            }]
        })

    def _on_dist_changed(self) -> None:
        if self._block_signals:
            return
        atmos_txt = self.cmb_atmos.currentText().lower()
        self._apply_dict({
            "disturbances.gaussian.enabled": self.chk_gauss.isChecked(),
            "disturbances.salt_pepper.enabled": self.chk_sp.isChecked(),
            "disturbances.poisson.enabled": self.chk_poisson.isChecked(),
            "disturbances.jitter.enabled": self.chk_jitter.isChecked(),
            "disturbances.platform.enabled": self.chk_drift.isChecked(),
            "disturbances.blur.enabled": self.chk_blur.isChecked(),
            "disturbances.atmosphere.kind": atmos_txt,
            "disturbances.atmosphere.enabled": (atmos_txt != "clear"),
        })

    def _on_seed_changed(self) -> None:
        if self._block_signals:
            return
        self._apply_dict({"seed": self.spn_seed.value()})

    def _randomise_seed(self) -> None:
        new_seed = random.randint(1, 999999)
        self.spn_seed.setValue(new_seed)

    def _apply_dict(self, overrides: dict[str, Any]) -> None:
        """Apply overrides through ConfigEditor, updating inline errors."""
        new_cfg, violations = self.editor.apply_overrides(overrides)
        if violations:
            err_msg = "\n".join(violations)
            self.lbl_error.setText(f"Configuration Error:\n{err_msg}")
            self.lbl_error.show()
            self.btn_start.setEnabled(False)
        else:
            self.lbl_error.hide()
            self.btn_start.setEnabled(True)
            if new_cfg is not None:
                self.config_changed.emit(new_cfg)


__all__ = ("ControlsPanel",)
