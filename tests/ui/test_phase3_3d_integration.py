"""Tests for Phase 3: 3D Space Simulation integration into Python SkyLock GUI."""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

from skylock.ui.main_window import MainWindow
from skylock.ui.web3d.server import Embedded3DServer, get_static_assets_path
from skylock.ui.web3d.view_3d import SpaceView3D


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """Fixture providing an offscreen QApplication instance."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Test A: Asset Resolution
# ---------------------------------------------------------------------------
def test_asset_resolution() -> None:
    """Verify that all required 3D assets exist in the resolved static directory."""
    assets_dir = get_static_assets_path()
    assert assets_dir.exists(), f"Static assets dir does not exist: {assets_dir}"

    index_html = assets_dir / "index.html"
    assert index_html.exists(), "index.html missing from static assets"

    assets_sub = assets_dir / "assets"
    assert assets_sub.exists(), "assets/ subdirectory missing"

    earth_glb = assets_sub / "earth.glb"
    assert earth_glb.exists(), "earth.glb missing from assets"
    assert earth_glb.stat().st_size > 500_000, "earth.glb appears truncated"

    sat1_glb = assets_sub / "satellite.glb"
    assert sat1_glb.exists(), "satellite.glb missing from assets"
    assert sat1_glb.stat().st_size > 1_000_000, "satellite.glb appears truncated"

    sat2_glb = assets_sub / "satellite2.glb"
    assert sat2_glb.exists(), "satellite2.glb missing from assets"
    assert sat2_glb.stat().st_size > 1_000_000, "satellite2.glb appears truncated"

    js_bundles = list(assets_sub.glob("*.js"))
    assert len(js_bundles) >= 1, "Compiled Three.js bundle missing from assets"


# ---------------------------------------------------------------------------
# Test B & C: Embedded Server & 3D Initialization
# ---------------------------------------------------------------------------
def test_embedded_server_lifecycle() -> None:
    """Verify that Embedded3DServer starts, binds an ephemeral port, and stops cleanly."""
    server = Embedded3DServer()
    port = server.start()
    assert port > 0, "Server failed to bind to an available port"
    assert server.is_alive(), "Server socket should be listening"

    url = server.get_url()
    assert url == f"http://127.0.0.1:{port}/index.html"

    server.stop()
    assert not server.is_alive(), "Server should not be alive after stop()"


def test_space_view_3d_widget(qapp: QApplication) -> None:
    """Verify SpaceView3D widget construction, geometry, and cleanup."""
    view = SpaceView3D()
    view.resize(640, 480)
    view.show()
    qapp.processEvents()

    assert view.width() == 640
    assert view.height() == 480
    assert view.current_pan == 90.0
    assert view.current_tilt == 0.0
    assert view.current_fov == 20.0

    view.cleanup()
    view.close()


# ---------------------------------------------------------------------------
# Test F, G, H, I, J, K: Gimbal Pose, FOV, and State Updates
# ---------------------------------------------------------------------------
def test_gimbal_pose_updates(qapp: QApplication) -> None:
    """Verify pan and tilt angle updates via SpaceView3D."""
    view = SpaceView3D()
    view.resize(400, 300)
    view.show()
    qapp.processEvents()

    view.set_gimbal_pose(15.0, -8.5)
    assert view.current_pan == 15.0
    assert view.current_tilt == -8.5

    view.set_gimbal_pose(-30.0, 45.0)
    assert view.current_pan == -30.0
    assert view.current_tilt == 45.0

    view.cleanup()
    view.close()


def test_camera_fov_updates(qapp: QApplication) -> None:
    """Verify camera FOV configuration via SpaceView3D."""
    view = SpaceView3D()
    view.resize(400, 300)
    view.show()
    qapp.processEvents()

    view.set_camera_fov(35.0)
    assert view.current_fov == 35.0

    view.set_camera_fov(12.5)
    assert view.current_fov == 12.5

    view.cleanup()
    view.close()


def test_state_dictionary_updates(qapp: QApplication) -> None:
    """Verify full state dictionary update via SpaceView3D."""
    view = SpaceView3D()
    view.resize(400, 300)
    view.show()
    qapp.processEvents()

    state = {
        "pan": 42.0,
        "tilt": -12.0,
        "fov": 25.0,
        "paused": True,
        "speed": 2.0,
    }
    view.update_state(state)
    assert view.current_pan == 42.0
    assert view.current_tilt == -12.0
    assert view.current_fov == 25.0

    view.cleanup()
    view.close()


# ---------------------------------------------------------------------------
# Test MainWindow Integration: Tabs, 3D View, and Actions
# ---------------------------------------------------------------------------
def test_main_window_contains_3d_view(qapp: QApplication) -> None:
    """Verify that MainWindow central area houses SpaceView3D as primary tab."""
    win = MainWindow()
    win.resize(1600, 900)
    win.show()
    qapp.processEvents()

    assert hasattr(win, "space_view_3d")
    assert win.space_view_3d is not None
    assert hasattr(win, "view_tabs")
    assert win.view_tabs.count() >= 2
    assert win.view_tabs.tabText(0) == "3D Space Simulation"
    assert win.view_tabs.tabText(1) == "Camera Sensor Feed"
    assert win.view_tabs.currentWidget() == win.space_view_3d

    # CameraView must also be retained
    assert hasattr(win, "camera_view")
    assert win.camera_view.width() > 0
    assert win.camera_view.height() > 0

    win.space_view_3d.cleanup()
    win.close()


def test_view_menu_3d_actions(qapp: QApplication) -> None:
    """Verify that View menu contains actions for 3D Space Simulation and Demo."""
    win = MainWindow()
    win.resize(1280, 720)
    win.show()
    qapp.processEvents()

    menubar = win.menuBar()
    actions = [a.text() for a in menubar.actions()]
    assert "&View" in actions

    # Find View menu
    view_action = [a for a in menubar.actions() if a.text() == "&View"][0]
    view_menu = view_action.menu()
    menu_texts = [a.text().replace("&", "") for a in view_menu.actions()]

    assert "3D Space Simulation" in menu_texts
    assert "Camera Sensor Feed" in menu_texts
    assert "Run 3D Gimbal Demo" in menu_texts

    win.space_view_3d.cleanup()
    win.close()


# ---------------------------------------------------------------------------
# Test Demonstration Mode
# ---------------------------------------------------------------------------
def test_3d_demonstration_mode(qapp: QApplication) -> None:
    """Verify that start_3d_demonstration switches to 3D tab and executes without error."""
    win = MainWindow()
    win.resize(1280, 720)
    win.show()
    qapp.processEvents()

    # Switch to 2D view first
    win.view_tabs.setCurrentWidget(win.camera_view)
    assert win.view_tabs.currentWidget() == win.camera_view

    # Trigger demonstration mode
    win.start_3d_demonstration()
    qapp.processEvents()

    # Must switch back to 3D view
    assert win.view_tabs.currentWidget() == win.space_view_3d
    assert win.space_view_3d.current_pan == 0.0
    assert win.space_view_3d.current_tilt == 0.0

    win.space_view_3d.cleanup()
    win.close()


# ---------------------------------------------------------------------------
# Test Window Resize & Clean Shutdown
# ---------------------------------------------------------------------------
def test_multi_resolution_resizing(qapp: QApplication) -> None:
    """Verify MainWindow resize across 1280x720, 1366x768, 1600x900, 1920x1080."""
    win = MainWindow()
    win.show()

    resolutions = [
        (1280, 720),
        (1366, 768),
        (1600, 900),
        (1920, 1080),
    ]

    for w, h in resolutions:
        win.resize(w, h)
        qapp.processEvents()
        size = win.size()
        assert size.width() == w
        assert size.height() == h
        assert win.space_view_3d.width() > 0
        assert win.space_view_3d.height() > 0

    win.space_view_3d.cleanup()
    win.close()
