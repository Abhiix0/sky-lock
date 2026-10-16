# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for SkyLock — Electro-Optical Tracking System.

Produces a portable ONEDIR release under dist/SkyLock-Portable.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Root directory of the repository
repo_root = Path.cwd().resolve()
src_dir = repo_root / "src"

# Collect static assets
static_assets = (str(src_dir / "skylock" / "ui" / "web3d" / "static"), "skylock/ui/web3d/static")

datas = [static_assets]
binaries = []
hiddenimports = [
    "skylock",
    "skylock.app",
    "skylock.app.cli",
    "skylock.app.factory",
    "skylock.app.main",
    "skylock.benchmark",
    "skylock.benchmark.catalog",
    "skylock.benchmark.report",
    "skylock.benchmark.runner",
    "skylock.benchmark.scenario",
    "skylock.config",
    "skylock.config.io",
    "skylock.config.models",
    "skylock.config.validation",
    "skylock.control",
    "skylock.control.controller",
    "skylock.control.pid",
    "skylock.core",
    "skylock.core.enums",
    "skylock.core.geometry",
    "skylock.core.los",
    "skylock.core.orbital_world",
    "skylock.core.sim_clock",
    "skylock.core.types",
    "skylock.metrics",
    "skylock.metrics.collector",
    "skylock.metrics.requirements",
    "skylock.simulation",
    "skylock.simulation.camera",
    "skylock.simulation.gimbal",
    "skylock.simulation.motion",
    "skylock.simulation.mp4_source",
    "skylock.simulation.orbital_source",
    "skylock.simulation.source",
    "skylock.simulation.targets",
    "skylock.simulation.disturbances",
    "skylock.simulation.disturbances.base",
    "skylock.simulation.disturbances.stack",
    "skylock.tracking",
    "skylock.tracking.candidate_tracker",
    "skylock.tracking.kalman",
    "skylock.tracking.search_patterns",
    "skylock.tracking.state_machine",
    "skylock.tracking.tracker",
    "skylock.vision",
    "skylock.vision.centroid",
    "skylock.vision.detector",
    "skylock.vision.preprocess",
    "skylock.ui",
    "skylock.ui.config_editor",
    "skylock.ui.config_model",
    "skylock.ui.main_window",
    "skylock.ui.settings",
    "skylock.ui.theme",
    "skylock.ui.worker",
    "skylock.ui.panels",
    "skylock.ui.panels.benchmark",
    "skylock.ui.panels.camera_feed_view",
    "skylock.ui.panels.configuration_view",
    "skylock.ui.panels.controls",
    "skylock.ui.panels.gimbal_control",
    "skylock.ui.panels.telemetry",
    "skylock.ui.web3d",
    "skylock.ui.web3d.server",
    "skylock.ui.web3d.view_3d",
    "skylock.ui.web3d.gimbal_cam_view",
    "skylock.ui.widgets",
    "skylock.ui.widgets.camera_view",
    "skylock.ui.widgets.no_wheel",
    "skylock.ui.widgets.state_timeline",
    "cv2",
    "numpy",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
]

# Collect PySide6 and QtWebEngine dependencies
pyside6_datas, pyside6_binaries, pyside6_hidden = collect_all("PySide6")
datas.extend(pyside6_datas)
binaries.extend(pyside6_binaries)
hiddenimports.extend(pyside6_hidden)

# Deduplicate
datas = list(set(datas))
hiddenimports = list(set(hiddenimports))

a = Analysis(
    [str(src_dir / "skylock" / "app" / "main.py")],
    pathex=[str(src_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "notebook", "jupyter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SkyLock",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Windowed GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SkyLock-Portable",
)
