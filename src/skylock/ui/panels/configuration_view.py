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
    """Central tab for visualization options and manual satellite orbit placement."""

    orbit_lines_toggled = Signal(bool)
    track_line_toggled = Signal(bool)
    tracking_beam_toggled = track_line_toggled  # Alias for backward compatibility
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

        # ─── Group 1: Visualization Controls ─────────────────────────
        grp_vis = QGroupBox("Visualization Controls")
        vis_layout = QVBoxLayout(grp_vis)
        vis_layout.setSpacing(8)

        # Control 1: Show Orbit Lines
        self.chk_orbit_lines = QCheckBox("Show Orbit Lines")
        self.chk_orbit_lines.setChecked(True)
        self.chk_orbit_lines.setToolTip("Toggle visibility of 3D orbital trajectory lines")
        self.chk_orbit_lines.toggled.connect(self.orbit_lines_toggled.emit)
        vis_layout.addWidget(self.chk_orbit_lines)

        # Control 2: Show Track Line
        self.chk_track_line = QCheckBox("Show Track Line")
        self.chk_track_line.setChecked(True)
        self.chk_track_line.setToolTip("Toggle visibility of laser tracking line between satellites")
        self.chk_track_line.toggled.connect(self.track_line_toggled.emit)
        self.chk_tracking_beam = self.chk_track_line  # Alias
        vis_layout.addWidget(self.chk_track_line)

        layout.addWidget(grp_vis)

        # ─── Group 2: Satellite Orbit Radii ──────────────────────────
        grp_placement = QGroupBox("Satellite Orbit Radii")
        placement_layout = QVBoxLayout(grp_placement)
        placement_layout.setSpacing(12)

        desc = QLabel(
            "Configure orbital radius for each satellite."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {theme.TEXT_SECONDARY.name()}; font-size: 11px;")
        placement_layout.addWidget(desc)

        # Control 3: Orbit Radius per satellite
        form_radii = QFormLayout()
        form_radii.setSpacing(8)

        self.spn_s1_radius = NoWheelDoubleSpinBox()
        self.spn_s1_radius.setRange(12.0, 50.0)
        self.spn_s1_radius.setValue(20.0)
        self.spn_s1_radius.setSingleStep(1.0)
        self.spn_s1_radius.setSuffix(" units")
        form_radii.addRow("Satellite 1 (S-1) Radius:", self.spn_s1_radius)

        self.spn_s2_radius = NoWheelDoubleSpinBox()
        self.spn_s2_radius.setRange(12.0, 50.0)
        self.spn_s2_radius.setValue(26.0)
        self.spn_s2_radius.setSingleStep(1.0)
        self.spn_s2_radius.setSuffix(" units")
        form_radii.addRow("Satellite 2 (S-2) Radius:", self.spn_s2_radius)

        placement_layout.addLayout(form_radii)

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
            },
            "s2": {
                "radius": self.spn_s2_radius.value(),
            },
        }
        self.orbits_changed.emit(data)

    def _on_reset_orbits(self) -> None:
        self.spn_s1_radius.setValue(20.0)
        self.spn_s2_radius.setValue(26.0)
        self._on_apply_orbits()
