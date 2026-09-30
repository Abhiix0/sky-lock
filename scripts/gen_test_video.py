"""Generate deterministic synthetic MP4 test video from SimulationSource."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from skylock.config.models import (
    CameraConfig,
    DetectionConfig,
    DisturbanceConfig,
    GaussianConfig,
    GimbalConfig,
    LineMotion,
    SkyLockConfig,
    TargetConfig,
    TargetSetConfig,
    TrackingConfig,
)
from skylock.simulation.source import FixedPointingGimbal, SimulationSource


def generate_test_video(
    out_path: str | Path,
    seconds: float = 2.0,
    seed: int = 42,
    fps: float = 30.0,
) -> Path:
    """Render a deterministic MP4 video using SimulationSource and write to out_path.

    Args:
        out_path: Target path for the generated MP4 file.
        seconds: Duration of the video in seconds.
        seed: Random seed for motion and disturbances.
        fps: Video framerate in Hz.

    Returns:
        Path to the written MP4 file.

    Raises:
        RuntimeError: If cv2.VideoWriter fails to initialize with mp4v codec.
    """
    out = Path(out_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    cam = CameraConfig(
        width=640,
        height=480,
        fov_h_deg=4.0,
        fov_v_deg=3.0,
        fps=fps,
    )
    target = TargetConfig(
        initial="fixed",
        initial_pos_deg=(0.1, 0.1),
        motion=LineMotion(speed_deg_s=0.25, heading_deg=45.0),
        size_px=10,
        brightness=220.0,
    )
    disturbances = DisturbanceConfig(
        gaussian=GaussianConfig(enabled=True, sigma_levels=5.0),
    )
    cfg = SkyLockConfig(
        camera=cam,
        target=TargetSetConfig(count=1, targets=(target,)),
        gimbal=GimbalConfig(initial=(0.0, 0.0)),
        detection=DetectionConfig(),
        tracking=TrackingConfig(),
        disturbances=disturbances,
        seed=seed,
    )

    source = SimulationSource(cfg, gimbal=FixedPointingGimbal())
    source.open()

    fourcc = cv2.VideoWriter.fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out), fourcc, fps, (cam.width, cam.height))
    if not writer.isOpened():
        source.close()
        raise RuntimeError(f"cv2.VideoWriter failed to open writer for codec mp4v at {out}")

    total_frames = max(1, round(seconds * fps))

    try:
        for _ in range(total_frames):
            frame = source.read()
            if frame is None:
                break
            bgr = cv2.cvtColor(frame.image, cv2.COLOR_GRAY2BGR)
            writer.write(bgr)
    finally:
        writer.release()
        source.close()

    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render deterministic MP4 video using SimulationSource."
    )
    parser.add_argument("--out", type=str, required=True, help="Output MP4 file path")
    parser.add_argument(
        "--seconds", type=float, default=2.0, help="Duration in seconds (default: 2.0)"
    )
    parser.add_argument("--seed", type=int, default=42, help="Simulation seed (default: 42)")
    parser.add_argument("--fps", type=float, default=30.0, help="Framerate in Hz (default: 30.0)")

    args = parser.parse_args()
    path = generate_test_video(
        out_path=args.out,
        seconds=args.seconds,
        seed=args.seed,
        fps=args.fps,
    )
    print(f"Generated test video: {path}")


if __name__ == "__main__":
    main()
