"""PySide6 3D Space View widget embedding WebGL Three.js simulation."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from skylock.ui.web3d.server import Embedded3DServer

logger = logging.getLogger(__name__)


class SpaceView3D(QWidget):
    """3D Space Visualization Widget embedding Earth, Satellites, Gimbal, and FOV frustum."""

    scene_ready = Signal()
    state_updated = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)

        self._server = Embedded3DServer()
        self._server.start()

        self._is_ready = False
        self._last_pan = 90.0
        self._last_tilt = 0.0
        self._last_fov = 20.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._web_view = QWebEngineView(self)
        layout.addWidget(self._web_view)

        # Configure WebEngine settings for hardware acceleration
        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self._web_view.loadFinished.connect(self._on_load_finished)

        # Load 3D scene from embedded local server
        url = self._server.get_url()
        self._web_view.load(QUrl(url))

    @property
    def is_ready(self) -> bool:
        """Whether the WebGL 3D scene is loaded and ready."""
        return self._is_ready

    @property
    def current_pan(self) -> float:
        """Current gimbal pan in degrees."""
        return self._last_pan

    @property
    def current_tilt(self) -> float:
        """Current gimbal tilt in degrees."""
        return self._last_tilt

    @property
    def current_fov(self) -> float:
        """Current camera FOV in degrees."""
        return self._last_fov

    def _on_load_finished(self, success: bool) -> None:
        """Invoked when web view finishes loading."""
        if success:
            self._is_ready = True
            logger.info("SpaceView3D WebGL scene loaded successfully")
            self.scene_ready.emit()
            # Push initial values
            self.set_gimbal_pose(self._last_pan, self._last_tilt)
            self.set_camera_fov(self._last_fov)
        else:
            logger.warning("SpaceView3D failed to load WebGL scene")

    def set_gimbal_pose(self, pan_deg: float, tilt_deg: float) -> None:
        """Command the 3D gimbal pan and tilt angles in degrees."""
        self._last_pan = float(pan_deg)
        self._last_tilt = float(tilt_deg)
        js = f"window.skylock3d?.setGimbalPose({self._last_pan}, {self._last_tilt});"
        self._web_view.page().runJavaScript(js)

    def set_camera_fov(self, fov_deg: float) -> None:
        """Update the 3D camera FOV and frustum geometry in degrees."""
        self._last_fov = float(fov_deg)
        js = f"window.skylock3d?.setCameraFov({self._last_fov});"
        self._web_view.page().runJavaScript(js)

    def update_state(self, state: dict[str, Any]) -> None:
        """Update 3D visualization state from authoritative Python dictionary."""
        if "pan" in state:
            self._last_pan = float(state["pan"])
        if "tilt" in state:
            self._last_tilt = float(state["tilt"])
        if "fov" in state:
            self._last_fov = float(state["fov"])

        state_json = json.dumps(state)
        js = f"window.skylock3d?.updateState({state_json});"
        self._web_view.page().runJavaScript(js)

    def set_paused(self, paused: bool) -> None:
        """Pause or resume the 3D orbit simulation."""
        js_val = "true" if paused else "false"
        js = f"window.skylock3d?.setPaused({js_val});"
        self._web_view.page().runJavaScript(js)

    def set_simulation_speed(self, speed: float) -> None:
        """Set simulation speed multiplier."""
        js = f"window.skylock3d?.setSimulationSpeed({float(speed)});"
        self._web_view.page().runJavaScript(js)

    def reset_view(self) -> None:
        """Reset the user orbit camera to default Earth view."""
        self._web_view.page().runJavaScript("window.skylock3d?.resetView();")

    def query_state(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Query current state from the JavaScript 3D layer asynchronously."""

        def _handle_result(res: Any) -> None:
            if isinstance(res, dict):
                self.state_updated.emit(res)
                callback(res)

        self._web_view.page().runJavaScript("window.skylock3d?.getState();", _handle_result)

    def closeEvent(self, event: Any) -> None:
        """Clean up embedded HTTP server when widget is closed."""
        self.cleanup()
        super().closeEvent(event)

    def cleanup(self) -> None:
        """Stop server and release resources."""
        if self._server is not None:
            self._server.stop()
