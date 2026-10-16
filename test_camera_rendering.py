"""
Test script to verify camera rendering is working.
Opens GUI and checks that WebGL scene initializes.
"""
import sys
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from skylock.ui.main_window import MainWindow

def test_camera_rendering():
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    # Wait for initialization
    def check_camera():
        camera_view = window.camera_feed
        gimbal_cam = camera_view.gimbal_cam
        
        print(f"Gimbal camera ready: {gimbal_cam.is_ready}")
        print(f"Active view mode: {camera_view._active_view_mode}")
        print(f"Selected satellite: {camera_view.selected_satellite()}")
        
        if gimbal_cam.is_ready:
            print("✅ Camera rendering initialized successfully")
            QTimer.singleShot(2000, app.quit)
        else:
            print("⏳ Waiting for camera to initialize...")
            QTimer.singleShot(1000, check_camera)
    
    QTimer.singleShot(3000, check_camera)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    test_camera_rendering()
