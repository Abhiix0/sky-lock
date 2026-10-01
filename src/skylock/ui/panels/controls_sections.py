"""Collapsible section builders for the ControlsPanel.

Each function creates a QGroupBox (optionally checkable/collapsible) populated
with the widgets listed in the G3 spec.  Keeping sections here keeps
controls.py under the ~450-line budget.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _linked_slider_spin(
    parent: QWidget,
    *,
    minimum: float,
    maximum: float,
    default: float,
    decimals: int = 2,
    step: float = 0.01,
    suffix: str = "",
    tooltip: str = "",
    slider_scale: int = 100,
) -> tuple[QSlider, QDoubleSpinBox]:
    """Create a linked slider + spin box pair.

    The slider operates on ints (value * slider_scale); signals are blocked
    while syncing to avoid recursive updates.
    """
    slider = QSlider(Qt.Orientation.Horizontal, parent)
    slider.setMinimum(int(minimum * slider_scale))
    slider.setMaximum(int(maximum * slider_scale))
    slider.setValue(int(default * slider_scale))

    spin = QDoubleSpinBox(parent)
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSingleStep(step)
    spin.setSuffix(suffix)
    spin.setValue(default)
    if tooltip:
        slider.setToolTip(tooltip)
        spin.setToolTip(tooltip)

    # Slider -> Spin (block spin signals)
    def _slider_changed(raw: int) -> None:
        spin.blockSignals(True)
        spin.setValue(raw / slider_scale)
        spin.blockSignals(False)

    # Spin -> Slider (block slider signals)
    def _spin_changed(val: float) -> None:
        slider.blockSignals(True)
        slider.setValue(int(val * slider_scale))
        slider.blockSignals(False)

    slider.valueChanged.connect(_slider_changed)
    spin.valueChanged.connect(_spin_changed)

    return slider, spin


# ---------------------------------------------------------------------------
# Disturbance magnitude section
# ---------------------------------------------------------------------------

class DisturbanceMagnitudeRow(QWidget):
    """A single disturbance: [checkbox] [slider] [spinbox] [unit label].

    Signals:
        enabled_changed(str, bool)  - (dist_name, enabled)
        value_changed(str, str, float) - (dist_name, field_key, new_value)
    """

    enabled_changed = Signal(str, bool)
    value_changed = Signal(str, str, float)

    def __init__(
        self,
        dist_name: str,
        field_key: str,
        *,
        label: str,
        unit: str,
        minimum: float,
        maximum: float,
        default: float,
        decimals: int = 2,
        step: float = 0.01,
        slider_scale: int = 100,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.dist_name = dist_name
        self.field_key = field_key

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.chk = QCheckBox(label, self)
        self.chk.setToolTip(f"Enable/disable {label}")

        tooltip = f"{unit}  [PS limit: {minimum}..{maximum}]"
        self.slider, self.spin = _linked_slider_spin(
            self,
            minimum=minimum,
            maximum=maximum,
            default=default,
            decimals=decimals,
            step=step,
            slider_scale=slider_scale,
            tooltip=tooltip,
        )
        self.lbl_unit = QLabel(unit, self)

        layout.addWidget(self.chk)
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.spin)
        layout.addWidget(self.lbl_unit)

        # Connect
        self.chk.toggled.connect(self._on_enabled)
        self.spin.valueChanged.connect(self._on_value)

    # ---- internal signals ----
    def _on_enabled(self, checked: bool) -> None:
        self.slider.setEnabled(checked)
        self.spin.setEnabled(checked)
        self.enabled_changed.emit(self.dist_name, checked)

    def _on_value(self, val: float) -> None:
        self.value_changed.emit(self.dist_name, self.field_key, val)

    # ---- programmatic sync ----
    def set_enabled_checked(self, enabled: bool) -> None:
        self.chk.blockSignals(True)
        self.chk.setChecked(enabled)
        self.slider.setEnabled(enabled)
        self.spin.setEnabled(enabled)
        self.chk.blockSignals(False)

    def set_value(self, val: float) -> None:
        self.spin.blockSignals(True)
        self.slider.blockSignals(True)
        self.spin.setValue(val)
        self.slider.setValue(int(val * (self.slider.maximum() / max(self.spin.maximum(), 1e-9))))
        self.spin.blockSignals(False)
        self.slider.blockSignals(False)


# ---------------------------------------------------------------------------
# Atmosphere section helpers
# ---------------------------------------------------------------------------

class AtmosphereSection(QWidget):
    """Mode combo + strength slider for atmosphere disturbance.

    Signals:
        atmos_changed(str, float) - (mode, strength)
    """

    atmos_changed = Signal(str, float)

    DISPLAY_TO_MODE = {
        "Clear": "clear",
        "Haze": "haze",
        "Fog": "fog",
        "Rain": "rain",
        "Low light": "low_light",
    }
    MODE_TO_DISPLAY = {v: k for k, v in DISPLAY_TO_MODE.items()}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.cmb_mode = QComboBox(self)
        self.cmb_mode.addItems(list(self.DISPLAY_TO_MODE.keys()))
        self.cmb_mode.setToolTip("Atmosphere mode [PS modes: clear/haze/fog/rain/low_light]")

        self.slider_strength, self.spn_strength = _linked_slider_spin(
            self,
            minimum=0.0,
            maximum=1.0,
            default=0.0,
            decimals=2,
            step=0.05,
            tooltip="Atmosphere strength [0..1]",
        )

        layout.addRow("Mode:", self.cmb_mode)
        str_row = QHBoxLayout()
        str_row.addWidget(self.slider_strength, stretch=1)
        str_row.addWidget(self.spn_strength)
        layout.addRow("Strength:", str_row)

        self.cmb_mode.currentIndexChanged.connect(self._on_changed)
        self.spn_strength.valueChanged.connect(self._on_changed)

    def _on_changed(self) -> None:
        display = self.cmb_mode.currentText()
        mode = self.DISPLAY_TO_MODE.get(display, "clear")
        self.atmos_changed.emit(mode, self.spn_strength.value())

    def sync(self, mode: str, strength: float) -> None:
        self.cmb_mode.blockSignals(True)
        self.spn_strength.blockSignals(True)
        self.slider_strength.blockSignals(True)

        display = self.MODE_TO_DISPLAY.get(mode, "Clear")
        idx = self.cmb_mode.findText(display)
        if idx >= 0:
            self.cmb_mode.setCurrentIndex(idx)
        self.spn_strength.setValue(strength)
        self.slider_strength.setValue(int(strength * 100))

        self.cmb_mode.blockSignals(False)
        self.spn_strength.blockSignals(False)
        self.slider_strength.blockSignals(False)


# ---------------------------------------------------------------------------
# Motion parameter pages (QStackedWidget)
# ---------------------------------------------------------------------------

class MotionParamsStack(QWidget):
    """Stacked pages for motion kind parameters.

    Each page has fields exactly matching the spec ranges.

    Signals:
        params_changed(str, dict) - (motion_kind, {field: value})
    """

    params_changed = Signal(str, dict)

    # (field_name, label, min, max, default, decimals, step, unit)
    FIELD_SPECS: dict[str, list[tuple[str, str, float, float, float, int, float, str]]] = {
        "line": [
            ("speed_deg_s", "Speed", 0.0, 2.0, 0.5, 2, 0.1, "°/s"),
            ("heading_deg", "Heading", -180.0, 180.0, 0.0, 1, 1.0, "°"),
        ],
        "circle": [
            ("radius_deg", "Radius", 0.1, 2.5, 1.0, 2, 0.1, "°"),
            ("period_s", "Period", 2.0, 60.0, 10.0, 1, 1.0, "s"),
            ("phase_rad", "Phase", -3.14, 3.14, 0.0, 2, 0.01, "rad"),
        ],
        "figure8": [
            ("width_deg", "Width", 0.2, 3.0, 1.5, 2, 0.1, "°"),
            ("height_deg", "Height", 0.2, 2.0, 1.0, 2, 0.1, "°"),
            ("period_s", "Period", 2.0, 60.0, 12.0, 1, 1.0, "s"),
        ],
        "random": [
            ("speed_deg_s", "Speed", 0.0, 2.0, 0.5, 2, 0.1, "°/s"),
            ("correlation_s", "Correlation", 0.2, 10.0, 2.0, 2, 0.1, "s"),
        ],
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget(self)
        self._pages: dict[str, QWidget] = {}
        self._spins: dict[str, dict[str, QDoubleSpinBox]] = {}

        for kind in ("line", "circle", "figure8", "random"):
            page = QWidget()
            form = QFormLayout(page)
            spins: dict[str, QDoubleSpinBox] = {}
            for fname, label, fmin, fmax, fdefault, fdec, fstep, funit in self.FIELD_SPECS[kind]:
                spin = QDoubleSpinBox(page)
                spin.setRange(fmin, fmax)
                spin.setDecimals(fdec)
                spin.setSingleStep(fstep)
                spin.setValue(fdefault)
                spin.setToolTip(f"{funit}  [PS limit: {fmin}..{fmax}]")
                spin.valueChanged.connect(self._on_param_changed)
                form.addRow(f"{label} ({funit}):", spin)
                spins[fname] = spin

            self._pages[kind] = page
            self._spins[kind] = spins
            self.stack.addWidget(page)

        layout.addWidget(self.stack)
        self._kind_to_index = {k: i for i, k in enumerate(("line", "circle", "figure8", "random"))}

    def set_kind(self, kind: str) -> None:
        idx = self._kind_to_index.get(kind, 0)
        self.stack.setCurrentIndex(idx)

    def current_kind(self) -> str:
        idx = self.stack.currentIndex()
        for k, i in self._kind_to_index.items():
            if i == idx:
                return k
        return "line"

    def get_params(self, kind: str) -> dict[str, float]:
        spins = self._spins.get(kind, {})
        return {fname: spin.value() for fname, spin in spins.items()}

    def sync(self, kind: str, params: dict[str, Any]) -> None:
        self.set_kind(kind)
        spins = self._spins.get(kind, {})
        for fname, spin in spins.items():
            if fname in params:
                spin.blockSignals(True)
                spin.setValue(float(params[fname]))
                spin.blockSignals(False)

    def _on_param_changed(self) -> None:
        kind = self.current_kind()
        self.params_changed.emit(kind, self.get_params(kind))


# ---------------------------------------------------------------------------
# MP4 input section
# ---------------------------------------------------------------------------

class Mp4InputSection(QWidget):
    """MP4 path + browse + probe status + fps_override + loop checkbox.

    Signals:
        path_changed(str)
        fps_override_changed(float | None)
        loop_changed(bool)
    """

    path_changed = Signal(str)
    fps_override_changed = Signal(object)  # float | None
    loop_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_path = QLabel("No file selected")
        self.lbl_path.setWordWrap(True)
        layout.addRow("Path:", self.lbl_path)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        layout.addRow("Status:", self.lbl_status)

        # FPS override (shown when fps unreadable)
        self.spn_fps_override = QDoubleSpinBox(self)
        self.spn_fps_override.setRange(1.0, 120.0)
        self.spn_fps_override.setDecimals(1)
        self.spn_fps_override.setValue(30.0)
        self.spn_fps_override.setToolTip(
            "FPS override [1..120] — set when container fps is unreadable"
        )
        self.spn_fps_override.hide()
        self.lbl_fps_note = QLabel("fps unreadable — set override:")
        self.lbl_fps_note.setStyleSheet("color: #F59E0B;")
        self.lbl_fps_note.hide()
        layout.addRow(self.lbl_fps_note)
        layout.addRow("FPS override:", self.spn_fps_override)

        self.chk_loop = QCheckBox("Loop video", self)
        self.chk_loop.setToolTip("Repeat video from beginning when end of stream is reached")
        layout.addRow(self.chk_loop)

        # Connect
        self.spn_fps_override.valueChanged.connect(
            lambda v: self.fps_override_changed.emit(v)
        )
        self.chk_loop.toggled.connect(self.loop_changed.emit)

    def set_path(self, path: str) -> None:
        self.lbl_path.setText(path or "No file selected")

    def show_probe_result(
        self,
        *,
        ok: bool,
        width: int = 0,
        height: int = 0,
        fps: float | None = None,
        frame_count: int = 0,
        error: str | None = None,
    ) -> None:
        if error:
            self.lbl_status.setText(f"❌ {error}")
            self.lbl_status.setStyleSheet("color: #EF4444;")
            self.lbl_fps_note.hide()
            self.spn_fps_override.hide()
        elif ok:
            fps_str = f"{fps:.1f}" if fps is not None else "unreadable"
            self.lbl_status.setText(f"✅ {width}×{height}  {fps_str} fps  {frame_count} frames")
            self.lbl_status.setStyleSheet("color: #10B981;")
            if fps is None:
                self.lbl_fps_note.show()
                self.spn_fps_override.show()
            else:
                self.lbl_fps_note.hide()
                self.spn_fps_override.hide()
        else:
            self.lbl_status.setText("No probe result")
            self.lbl_status.setStyleSheet("")
            self.lbl_fps_note.hide()
            self.spn_fps_override.hide()

    def sync(self, mp4_path: str, loop: bool, fps_override: float | None) -> None:
        self.lbl_path.setText(mp4_path or "No file selected")
        self.chk_loop.blockSignals(True)
        self.chk_loop.setChecked(loop)
        self.chk_loop.blockSignals(False)
        if fps_override is not None:
            self.spn_fps_override.blockSignals(True)
            self.spn_fps_override.setValue(fps_override)
            self.spn_fps_override.blockSignals(False)


# ---------------------------------------------------------------------------
# Presets dropdown
# ---------------------------------------------------------------------------

class PresetsDropdown(QWidget):
    """Presets combo box.

    Signals:
        preset_selected(str) - preset name key
    """

    preset_selected = Signal(str)

    PRESETS = {
        "(select preset)": None,
        "Clear (no disturbances)": "preset_clear",
        "Haze": "preset_haze",
        "Fog": "preset_fog",
        "Rain": "preset_rain",
        "Low Light": "preset_low_light",
        "Max Noise (PS §6)": "preset_spec_max_noise",
        "Max Jitter (PS §6)": "preset_spec_max_jitter",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.cmb = QComboBox(self)
        self.cmb.setToolTip("Apply a disturbance preset — replaces all disturbance settings")
        self.cmb.addItems(list(self.PRESETS.keys()))
        layout.addWidget(QLabel("Preset:", self))
        layout.addWidget(self.cmb, stretch=1)

        self.cmb.currentIndexChanged.connect(self._on_selected)

    def _on_selected(self, idx: int) -> None:
        text = self.cmb.itemText(idx)
        fn_name = self.PRESETS.get(text)
        if fn_name:
            self.preset_selected.emit(fn_name)

    def reset_selection(self) -> None:
        self.cmb.blockSignals(True)
        self.cmb.setCurrentIndex(0)
        self.cmb.blockSignals(False)


__all__ = (
    "AtmosphereSection",
    "DisturbanceMagnitudeRow",
    "MotionParamsStack",
    "Mp4InputSection",
    "PresetsDropdown",
)
