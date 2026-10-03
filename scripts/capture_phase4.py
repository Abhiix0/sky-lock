"""Generate Phase 4 demonstration screenshots."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from skylock.ui import theme
from skylock.ui.main_window import MainWindow

app = QApplication(sys.argv)
theme.apply_theme(app)

window = MainWindow()
window.resize(1600, 900)
window.show()

# Wait 3 seconds for WebGL 3D scene to load assets and render
loop = QEventLoop()
QTimer.singleShot(3500, loop.quit)
loop.exec()

artifacts_dir = Path("C:/Users/vedik/.gemini/antigravity-ide/brain/6a69fa1e-ff37-4840-8300-4a14b8d6375d")
artifacts_dir.mkdir(parents=True, exist_ok=True)

# 1. Capture 3D Space Simulation view
pixmap1 = window.grab()
p1 = artifacts_dir / "phase4_3d_simulation_1600x900.png"
pixmap1.save(str(p1))
print(f"Saved: {p1}")

# 2. Switch to Configuration tab and capture
window.view_tabs.setCurrentWidget(window.configuration_view)
app.processEvents()
time.sleep(0.5)
app.processEvents()

pixmap2 = window.grab()
p2 = artifacts_dir / "phase4_configuration_tab_1600x900.png"
pixmap2.save(str(p2))
print(f"Saved: {p2}")

window.space_view_3d.cleanup()
window.close()
app.quit()
