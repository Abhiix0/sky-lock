#!/usr/bin/env python3
"""Headless test to measure wall FPS of the worker timer.

Run with: QT_QPA_PLATFORM=offscreen python scripts/test_wall_fps.py
"""

import os
import sys
import time

# Set offscreen platform before importing Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QThread, QTimer

from skylock.config.models import SkyLockConfig
from skylock.ui.worker import SessionWorker


def test_wall_fps(target_fps: float = 30.0, duration_s: float = 3.0) -> None:
    """Measure actual wall FPS achieved by the worker timer."""
    app = QCoreApplication(sys.argv)
    
    # Build config with target FPS
    config = SkyLockConfig.from_dict({"camera": {"fps": target_fps}})
    
    # Create worker thread
    worker_thread = QThread()
    worker = SessionWorker(config)
    worker.moveToThread(worker_thread)
    worker_thread.started.connect(worker.initialize)
    
    # Track frame count
    frame_count = [0]
    start_time = [0.0]
    
    def on_frame(_frame_view):
        if frame_count[0] == 0:
            start_time[0] = time.perf_counter()
        frame_count[0] += 1
    
    worker.frame_ready.connect(on_frame)
    
    # Auto-stop after duration
    def stop_test():
        worker.stop_running()
        elapsed = time.perf_counter() - start_time[0]
        if frame_count[0] > 0:
            measured_fps = frame_count[0] / elapsed
            print(f"Target FPS: {target_fps:.1f}")
            print(f"Frames: {frame_count[0]}")
            print(f"Elapsed: {elapsed:.3f} s")
            print(f"Measured Wall FPS: {measured_fps:.2f}")
            print(f"Achievement: {(measured_fps / target_fps * 100):.1f}%")
            
            if measured_fps >= target_fps:
                print("✓ PASS: Wall FPS >= target")
                sys.exit(0)
            else:
                print("✗ FAIL: Wall FPS < target")
                sys.exit(1)
        else:
            print("✗ FAIL: No frames captured")
            sys.exit(1)
    
    QTimer.singleShot(int(duration_s * 1000) + 500, stop_test)
    
    # Start worker
    worker_thread.start()
    worker.start_running()
    
    app.exec()


if __name__ == "__main__":
    print("Testing wall FPS with PySide6 offscreen platform...")
    test_wall_fps(target_fps=30.0, duration_s=3.0)
