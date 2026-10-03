"""Central view tab for configuring 3D space visualization and satellite orbits."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from skylock.ui import theme
from skylock.ui.widgets.no_wheel import NoWheelDoubleSpinBox


class ConfigurationView(QWidget):
    """Central tab for visualization options and manual physical satellite orbit placement."""

    orbit_lines_toggled = Signal(bool)
    camera_fov_toggled = Signal(bool)
    optical_axis_toggled = Signal(bool)
    tracking_beam_toggled = Signal(bool)
    orbits_changed = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # ─── Group 1: Orbit Visualization ───────────────────────────
        grp_orbits = QGroupBox("Orbit Visualization")
        orbit_layout = QVBoxLayout(grp_orbits)
        orbit_layout.setSpacing(8)

        self.chk_orbit_lines = QCheckBox("Show Orbit Lines")
        self.chk_orbit_lines.setChecked(True)
        self.chk_orbit_lines.setToolTip("Toggle visibility of 3D orbital trajectory lines")
        self.chk_orbit_lines.toggled.connect(self.orbit_lines_toggled.emit)
        orbit_layout.addWidget(self.chk_orbit_lines)

        layout.addWidget(grp_orbits)

        # ─── Group 2: Camera Visualization ──────────────────────────
        grp_camera = QGroupBox("Camera Visualization")
        cam_layout = QVBoxLayout(grp_camera)
        cam_layout.setSpacing(8)

        self.chk_camera_fov = QCheckBox("Show Camera FOV (Frustum)")
        self.chk_camera_fov.setChecked(True)
        self.chk_camera_fov.setToolTip(
            "Display perspective camera sensor field-of-view originating from S-1 gimbal"
        )
        self.chk_camera_fov.toggled.connect(self.camera_fov_toggled.emit)
        cam_layout.addWidget(self.chk_camera_fov)

        self.chk_optical_axis = QCheckBox("Show Optical Axis")
        self.chk_optical_axis.setChecked(True)
        self.chk_optical_axis.setToolTip("Display central optical boresight ray from S-1 sensor")
        self.chk_optical_axis.toggled.connect(self.optical_axis_toggled.emit)
        cam_layout.addWidget(self.chk_optical_axis)

        self.chk_tracking_beam = QCheckBox(
            "Show Optical Tracking Beam (when Line-of-Sight is clear)"
        )
        self.chk_tracking_beam.setChecked(True)
        self.chk_tracking_beam.setToolTip(
            "Display dynamic optical tracking beam from S-1 aperture to S-2 when in FOV and clear"
        )
        self.chk_tracking_beam.toggled.connect(self.tracking_beam_toggled.emit)
        cam_layout.addWidget(self.chk_tracking_beam)

        layout.addWidget(grp_camera)

        # ─── Group 3: Satellite Placement (Max 2 Satellites) ────────
        grp_placement = QGroupBox("Satellite Placement & Constrained Orbits (Max 2 Satellites)")
        placement_layout = QVBoxLayout(grp_placement)
        placement_layout.setSpacing(12)

        desc = QLabel(
            "Configure physical orbital elements. S-1 is Observer; S-2 is Target. "
            "Continuous motion is strictly constrained to valid orbital planes."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {theme.TEXT_SECONDARY.name()}; font-size: 11px;")
        placement_layout.addWidget(desc)

        # Subgroup: Satellite 1 (Observer)
        grp_s1 = QGroupBox("Satellite 1 — Observer Platform (Camera & Gimbal Mount)")
        form_s1 = QFormLayout(grp_s1)
        form_s1.setSpacing(6)

        self.spn_s1_radius = NoWheelDoubleSpinBox()
        self.spn_s1_radius.setRange(12.0, 50.0)
        self.spn_s1_radius.setValue(20.0)
        self.spn_s1_radius.setSingleStep(1.0)
        self.spn_s1_radius.setSuffix(" units")
        form_s1.addRow("Orbit Radius:", self.spn_s1_radius)

        self.spn_s1_inc = NoWheelDoubleSpinBox()
        self.spn_s1_inc.setRange(-90.0, 90.0)
        self.spn_s1_inc.setValue(25.0)
        self.spn_s1_inc.setSingleStep(5.0)
        self.spn_s1_inc.setSuffix("°")
        form_s1.addRow("Inclination:", self.spn_s1_inc)

        self.spn_s1_speed = NoWheelDoubleSpinBox()
        self.spn_s1_speed.setRange(-2.0, 2.0)
        self.spn_s1_speed.setValue(0.3)
        self.spn_s1_speed.setSingleStep(0.05)
        self.spn_s1_speed.setDecimals(2)
        self.spn_s1_speed.setSuffix(" rad/s")
        form_s1.addRow("Orbital Speed / Dir:", self.spn_s1_speed)

        self.spn_s1_phase = NoWheelDoubleSpinBox()
        self.spn_s1_phase.setRange(0.0, 360.0)
        self.spn_s1_phase.setValue(0.0)
        self.spn_s1_phase.setSingleStep(10.0)
        self.spn_s1_phase.setSuffix("°")
        form_s1.addRow("Initial Phase:", self.spn_s1_phase)

        placement_layout.addWidget(grp_s1)

        # Subgroup: Satellite 2 (Target)
        grp_s2 = QGroupBox("Satellite 2 — Target Platform (Optical Beacon)")
        form_s2 = QFormLayout(grp_s2)
        form_s2.setSpacing(6)

        self.spn_s2_radius = NoWheelDoubleSpinBox()
        self.spn_s2_radius.setRange(12.0, 50.0)
        self.spn_s2_radius.setValue(26.0)
        self.spn_s2_radius.setSingleStep(1.0)
        self.spn_s2_radius.setSuffix(" units")
        form_s2.addRow("Orbit Radius:", self.spn_s2_radius)

        self.spn_s2_inc = NoWheelDoubleSpinBox()
        self.spn_s2_inc.setRange(-90.0, 90.0)
        self.spn_s2_inc.setValue(65.0)
        self.spn_s2_inc.setSingleStep(5.0)
        self.spn_s2_inc.setSuffix("°")
        form_s2.addRow("Inclination:", self.spn_s2_inc)

        self.spn_s2_speed = NoWheelDoubleSpinBox()
        self.spn_s2_speed.setRange(-2.0, 2.0)
        self.spn_s2_speed.setValue(0.2)
        self.spn_s2_speed.setSingleStep(0.05)
        self.spn_s2_speed.setDecimals(2)
        self.spn_s2_speed.setSuffix(" rad/s")
        form_s2.addRow("Orbital Speed / Dir:", self.spn_s2_speed)

        self.spn_s2_phase = NoWheelDoubleSpinBox()
        self.spn_s2_phase.setRange(0.0, 360.0)
        self.spn_s2_phase.setValue(180.0)
        self.spn_s2_phase.setSingleStep(10.0)
        self.spn_s2_phase.setSuffix("°")
        form_s2.addRow("Initial Phase:", self.spn_s2_phase)

        placement_layout.addWidget(grp_s2)

        # Placement action buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        self.btn_apply = QPushButton("Apply Orbit Parameters")
        self.btn_apply.setStyleSheet("QPushButton { font-weight: bold; }")
        self.btn_apply.clicked.connect(self._on_apply_orbits)
        btn_box.addWidget(self.btn_apply)

        self.btn_reset_orbits = QPushButton("Reset Orbits to Defaults")
        self.btn_reset_orbits.clicked.connect(self._on_reset_orbits)
        btn_box.addWidget(self.btn_reset_orbits)

        placement_layout.addLayout(btn_box)
        layout.addWidget(grp_placement)

        layout.addStretch(1)
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def _on_apply_orbits(self) -> None:
        data: dict[str, Any] = {
            "s1": {
                "radius": self.spn_s1_radius.value(),
                "inclination": self.spn_s1_inc.value(),
                "speed": self.spn_s1_speed.value(),
                "phase": self.spn_s1_phase.value(),
            },
            "s2": {
                "radius": self.spn_s2_radius.value(),
                "inclination": self.spn_s2_inc.value(),
                "speed": self.spn_s2_speed.value(),
                "phase": self.spn_s2_phase.value(),
            },
        }
        self.orbits_changed.emit(data)

    def _on_reset_orbits(self) -> None:
        self.spn_s1_radius.setValue(20.0)
        self.spn_s1_inc.setValue(25.0)
        self.spn_s1_speed.setValue(0.3)
        self.spn_s1_phase.setValue(0.0)

        self.spn_s2_radius.setValue(26.0)
        self.spn_s2_inc.setValue(65.0)
        self.spn_s2_speed.setValue(0.2)
        self.spn_s2_phase.setValue(180.0)

        self._on_apply_orbits()
