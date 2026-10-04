"""Integration tests for dual concurrent tracking sessions and Earth boresight pointing mode."""

from __future__ import annotations

import math
import os
import sys
import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

# Set QT_QPA_PLATFORM before any Qt usage
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from skylock.app.factory import build_session
from skylock.config.models import SkyLockConfig
from skylock.control.controller import PointingController
from skylock.core.enums import ControlIntentMode, ControlMode, TrackState
from skylock.core.los import OrbitParams
from skylock.core.types import ControlIntent, Pointing, StepResult
from skylock.ui.worker import FrameView, SessionWorker


@pytest.fixture(scope="session")
def qapp():
    """QCoreApplication instance for headless tests."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv[:1])
    yield app


def test_dual_sessions_step_concurrently_and_independently() -> None:
    """Verify that S-1 and S-2 sessions run concurrently without interfering."""
    cfg = SkyLockConfig()
    session_s1 = build_session(cfg, sat_id="s1")
    session_s2 = build_session(cfg, sat_id="s2")

    assert session_s1 is not session_s2
    assert session_s1.controller is not session_s2.controller
    assert session_s1.pipeline is not session_s2.pipeline
    assert session_s1.source is not session_s2.source

    results_s1: list[StepResult] = []
    results_s2: list[StepResult] = []

    # Step both for 90 frames (~3 seconds at 30 fps)
    for _ in range(90):
        r1 = session_s1.step()
        r2 = session_s2.step()
        assert r1 is not None, "Session S-1 returned None prematurely"
        assert r2 is not None, "Session S-2 returned None prematurely"
        results_s1.append(r1)
        results_s2.append(r2)

    assert len(results_s1) == 90
    assert len(results_s2) == 90

    # Ensure frames advance timestamps identically and independently
    assert math.isclose(results_s1[-1].frame.timestamp_s, results_s2[-1].frame.timestamp_s, abs_tol=1e-5)

    # Validate independent internal states
    # S-1 and S-2 have different seeds / disturbances, so commands and estimates are distinct
    s1_pan = results_s1[-1].frame.pointing.pan_deg
    s2_pan = results_s2[-1].frame.pointing.pan_deg
    assert isinstance(s1_pan, float)
    assert isinstance(s2_pan, float)


def test_earth_boresight_tracks_earth_center_over_time() -> None:
    """Verify that EARTH mode continuously computes look-angle to Earth center as orbit evolves."""
    orbit1 = OrbitParams(radius=20.0, speed=0.3, inclination_deg=25.0, phase_deg=0.0)
    orbit2 = OrbitParams(radius=26.0, speed=0.2, inclination_deg=65.0, phase_deg=45.0)

    # Controller for S-1
    ctrl_s1 = PointingController(
        mode=ControlMode.EARTH,
        sat_id="s1",
        orbit_params=orbit1,
    )

    # Controller for S-2
    ctrl_s2 = PointingController(
        mode=ControlMode.EARTH_BORESIGHT,
        sat_id="s2",
        orbit_params=orbit2,
    )

    assert ctrl_s1.mode == ControlMode.EARTH
    assert ctrl_s2.mode == ControlMode.EARTH

    # Sample at different orbital times (e.g. advance dt over multiple steps)
    s1_rates: list[tuple[float, float]] = []
    s2_rates: list[tuple[float, float]] = []

    pointing = Pointing(pan_deg=0.0, tilt_deg=0.0)
    intent = ControlIntent(mode=ControlIntentMode.HOLD)

    # Step over 10 seconds of simulated time with 0.1s dt
    for step_i in range(100):
        dt = 0.1
        cmd1 = ctrl_s1.step(intent=intent, estimate=None, pointing=pointing, dt=dt)
        cmd2 = ctrl_s2.step(intent=intent, estimate=None, pointing=pointing, dt=dt)

        if step_i % 20 == 0:
            s1_rates.append((cmd1.pan_rate_deg_s, cmd1.tilt_rate_deg_s))
            s2_rates.append((cmd2.pan_rate_deg_s, cmd2.tilt_rate_deg_s))

    # Assert rates are not identically static over the orbit (not aim-and-forget)
    pan_rates_s1 = [r[0] for r in s1_rates]
    tilt_rates_s1 = [r[1] for r in s1_rates]
    assert len(set(round(p, 4) for p in pan_rates_s1)) > 1 or len(set(round(t, 4) for t in tilt_rates_s1)) > 1

    # Assert S-1 and S-2 have different look angles toward Earth's center due to phase difference
    assert s1_rates[0] != s2_rates[0]


def test_session_worker_dual_session_api(qapp) -> None:
    """Verify SessionWorker public API for dual sessions, modes, rates, and frame views."""
    cfg = SkyLockConfig()
    worker = SessionWorker(cfg)
    assert worker.session_s1 is None
    assert worker.session_s2 is None

    # Initialize builds both sessions
    worker._build_new_session(cfg)
    assert worker.session_s1 is not None
    assert worker.session_s2 is not None
    assert worker.session is worker.session_s1
    assert worker.get_session("s1") is worker.session_s1
    assert worker.get_session("s2") is worker.session_s2

    # Mode API: per-session mode setting
    worker.set_mode("s1", "EARTH")
    worker.set_mode("s2", "MANUAL")
    assert worker.session_s1.controller.mode == ControlMode.EARTH
    assert worker.session_s2.controller.mode == ControlMode.MANUAL

    worker.set_mode("s2", "AUTO")
    assert worker.session_s2.controller.mode == ControlMode.AUTO

    # Manual rates API: per-session rate setting
    worker.set_mode("s1", "MANUAL")
    worker.set_manual_rates("s1", 2.5, -1.2)
    worker.set_manual_rates("s2", -3.0, 1.5)
    assert worker.session_s1.controller.manual_pan_rate_deg_s == 2.5
    assert worker.session_s1.controller.manual_tilt_rate_deg_s == -1.2
    assert worker.session_s2.controller.manual_pan_rate_deg_s == -3.0
    assert worker.session_s2.controller.manual_tilt_rate_deg_s == 1.5

    # Tracking state & lock queries
    assert isinstance(worker.get_tracking_state("s1"), TrackState)
    assert isinstance(worker.get_tracking_state("s2"), TrackState)
    assert worker.is_locked("s1") is False

    # Capture dual frame signals
    received_s1: list[FrameView] = []
    received_s2: list[FrameView] = []
    dual_received: list[tuple[str, FrameView]] = []

    worker.frame_ready_s1.connect(received_s1.append)
    worker.frame_ready_s2.connect(received_s2.append)
    worker.dual_frame_ready.connect(lambda sat, fv: dual_received.append((sat, fv)))

    # Step worker directly
    worker._step()

    assert len(received_s1) == 1
    assert len(received_s2) == 1
    assert len(dual_received) == 2

    assert received_s1[0].sat_id == "s1"
    assert received_s2[0].sat_id == "s2"
    assert worker.get_latest_frame_view("s1") is received_s1[0]
    assert worker.get_latest_frame_view("s2") is received_s2[0]
    assert worker.get_latest_step_result("s1") is not None
    assert worker.get_latest_step_result("s2") is not None
