"""Reproducible Windows PyInstaller build script for SkyLock.

Builds a standalone portable directory under dist/SkyLock-Portable and
creates a distributable archive dist/SkyLock-Portable.zip.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "dist"
    portable_dir = dist_dir / "SkyLock-Portable"
    spec_file = repo_root / "packaging" / "skylock.spec"

    print(f"=== SkyLock Windows Executable Build ===")
    print(f"Repository Root: {repo_root}")
    print(f"Spec File: {spec_file}")

    if not spec_file.exists():
        print(f"Error: Spec file not found at {spec_file}", file=sys.stderr)
        return 1

    # Clean previous portable output
    if portable_dir.exists():
        print(f"Cleaning previous build at {portable_dir}...")
        shutil.rmtree(portable_dir, ignore_errors=True)

    # Run PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(repo_root / "build"),
        str(spec_file),
    ]

    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=repo_root)
    if result.returncode != 0:
        print("PyInstaller build failed!", file=sys.stderr)
        return result.returncode

    exe_path = portable_dir / "SkyLock.exe"
    if not exe_path.exists():
        print(f"Error: Expected executable not found at {exe_path}", file=sys.stderr)
        return 1

    print(f"\nExecutable successfully created: {exe_path}")

    # Write release README
    readme_content = """SkyLock — Electro-Optical Tracking System
==================================================
Version: 0.1.0
Target Platform: Windows 10 / 11 (x64)

LAUNCH INSTRUCTIONS:
1. Double-click SkyLock.exe to launch the application.
2. The 3D Space Simulation will automatically begin running upon launch.
3. Switch between "3D Space Simulation" and "Camera Sensor Feed" using the central tabs or the View menu.
4. Select observer satellite via the primary dropdown:
   - "S-1 observing S-2" (Host is S-1, Target is S-2)
   - "S-2 observing S-1" (Host is S-2, Target is S-1)
5. Gimbal steering can be switched between AUTO (autonomous tracking controller) and MANUAL (Arrow keys or W/A/S/D).

DATA & STORAGE LOCATIONS:
- User preferences, window layout, and dock states are saved to:
  %LOCALAPPDATA%\\SkyLock or Windows Registry (HKCU\\Software\\SkyLock\\SkyLockGUI)
- No temporary files are extracted into protected directories.
- No Python installation or developer dependencies are required to run this release.

SYSTEM REQUIREMENTS:
- Windows 10 version 1809 or newer, or Windows 11 (64-bit).
- OpenGL / WebGL compatible GPU or software rasterizer.
- Minimum display resolution: 1280x720 (recommended: 1920x1080).
"""
    readme_path = portable_dir / "README.txt"
    readme_path.write_text(readme_content, encoding="utf-8")
    print(f"Wrote release documentation to {readme_path}")

    # Create portable zip archive
    zip_path = dist_dir / "SkyLock-Portable.zip"
    print(f"Creating portable zip archive: {zip_path}...")
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(portable_dir):
            for file in files:
                abs_file = Path(root) / file
                rel_path = Path("SkyLock-Portable") / abs_file.relative_to(portable_dir)
                zf.write(abs_file, rel_path)

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Archive successfully created: {zip_path} ({zip_size_mb:.1f} MB)")
    print("\n=== Release Build Complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
