"""PySide6 3D Gimbal POV View widget embedding first-person Three.js simulation."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from skylock.ui.web3d.server import Embedded3DServer

logger = logging.getLogger(__name__)


class GimbalCamView(QWidget):
    """First-person perspective 3D gimbal view mounted on a satellite looking toward the target."""

    scene_ready = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        server: Embedded3DServer | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(320, 240)

        self._server = server or Embedded3DServer.get_shared_server()

        self._is_ready = False
        self._mount_sat = "s1"
        self._last_pan = 0.0
        self._last_tilt = 0.0
        self._last_fov = 3.0
        self._is_paused = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._web_view = QWebEngineView(self)
        layout.addWidget(self._web_view, stretch=1)

        # Configure WebEngine settings for hardware acceleration
        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self._web_view.loadFinished.connect(self._on_load_finished)

        # Load Gimbal POV 3D scene from embedded local server
        url = self._server.get_url("gimbal/index.html")
        self._web_view.load(QUrl(url))

    @property
    def is_ready(self) -> bool:
        """Whether the WebGL 3D scene is loaded and ready."""
        return self._is_ready

    @property
    def mount(self) -> str:
        """Currently mounted satellite ID ('s1' or 's2')."""
        return self._mount_sat

    @property
    def mount_satellite(self) -> str:
        """Currently mounted satellite ID ('s1' or 's2')."""
        return self._mount_sat

    @property
    def is_paused(self) -> bool:
        """Whether the 3D orbital clock is paused."""
        return self._is_paused

    @property
    def current_pan(self) -> float:
        """Current gimbal pan in degrees."""
        return self._last_pan

    @property
    def last_pan(self) -> float:
        """Last commanded gimbal pan in degrees."""
        return self._last_pan

    @property
    def current_tilt(self) -> float:
        """Current gimbal tilt in degrees."""
        return self._last_tilt

    @property
    def last_tilt(self) -> float:
        """Last commanded gimbal tilt in degrees."""
        return self._last_tilt

    @property
    def current_fov(self) -> float:
        """Current camera FOV in degrees."""
        return self._last_fov

    @property
    def last_fov(self) -> float:
        """Last commanded camera FOV in degrees."""
        return self._last_fov

    def _on_load_finished(self, success: bool) -> None:
        """Invoked when web view finishes loading."""
        if success:
            self._is_ready = True
            logger.info("GimbalCamView WebGL scene loaded successfully")
            self.scene_ready.emit()
            # Push initial values
            self.set_mount(self._mount_sat)
            self.set_pose(self._last_pan, self._last_tilt)
            self.set_fov(self._last_fov)
            self.set_paused(self._is_paused)
        else:
            logger.warning("GimbalCamView failed to load WebGL scene")

    def set_pose(self, pan_deg: float, tilt_deg: float) -> None:
        """Command the gimbal camera orientation in degrees."""
        self._last_pan = float(pan_deg)
        self._last_tilt = float(tilt_deg)
        js = f"window.gimbalcam?.setPose({self._last_pan}, {self._last_tilt});"
        self._web_view.page().runJavaScript(js)

    def set_fov(self, fov_deg: float) -> None:
        """Update the 3D gimbal camera FOV in degrees."""
        self._last_fov = float(fov_deg)
        js = f"window.gimbalcam?.setFov({self._last_fov});"
        self._web_view.page().runJavaScript(js)

    def set_mount(self, sat_id: str) -> None:
        """Set which satellite hosts the first-person gimbal camera ('s1' or 's2')."""
        clean_id = str(sat_id).lower().replace("-", "")
        self._mount_sat = "s2" if clean_id in ("s2", "sat2", "2") else "s1"
        js = f"window.gimbalcam?.setMount('{self._mount_sat}');"
        self._web_view.page().runJavaScript(js)

    def set_paused(self, paused: bool) -> None:
        """Pause or resume the 3D orbital clock."""
        self._is_paused = bool(paused)
        js = f"window.gimbalcam?.setPaused({str(self._is_paused).lower()});"
        self._web_view.page().runJavaScript(js)

    def set_simulation_speed(self, speed: float) -> None:
        """Set simulation speed multiplier."""
        js = f"window.gimbalcam?.setSimulationSpeed({float(speed)});"
        self._web_view.page().runJavaScript(js)

    def set_satellite_orbit(
        self,
        sat_id: str,
        radius: float,
        inc_deg: float,
        speed: float,
        phase_deg: float,
    ) -> None:
        """Configure orbit parameters for a satellite."""
        js = (
            f"window.gimbalcam?.setSatelliteOrbit('{sat_id}', {float(radius)}, "
            f"{float(inc_deg)}, {float(speed)}, {float(phase_deg)});"
        )
        self._web_view.page().runJavaScript(js)

    def set_time(self, time_sec: float) -> None:
        """Synchronize the simulation time directly (seconds)."""
        js = f"window.gimbalcam?.setTime({float(time_sec)});"
        self._web_view.page().runJavaScript(js)

    def reset_pose(self) -> None:
        """Reset gimbal camera to neutral pose (pan=0°, tilt=0°, fov=3°)."""
        self._last_pan = 0.0
        self._last_tilt = 0.0
        self._last_fov = 3.0
        self.set_pose(0.0, 0.0)
        self.set_fov(3.0)

    def get_state(
        self,
        callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any] | None:
        """Query internal state of the 3D gimbal scene."""
        if callback is not None:
            js = "window.gimbalcam ? window.gimbalcam.getState() : null;"
            self._web_view.page().runJavaScript(js, callback)
            return None
        return {
            "mount": self._mount_sat,
            "pan": self._last_pan,
            "tilt": self._last_tilt,
            "fov": self._last_fov,
            "is_paused": self._is_paused,
        }

    def cleanup(self) -> None:
        """Clean up view resources."""
        self._web_view.stop()


__all__ = ("GimbalCamView",)
