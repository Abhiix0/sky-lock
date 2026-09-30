"""Performance measurement script.

Measures per-stage timing at 640×480 with all disturbances enabled.
Runs >= 1000 frames, 3 repeats. Writes JSON to runs/perf/.

Usage:
    python scripts/perf_report.py [--frames N] [--repeats R] [--out runs/perf]
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

# Ensure src/ is on the path when run directly
_repo_root = Path(__file__).parents[1]
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src"))

import cv2  # noqa: E402

from skylock.config.models import (  # noqa: E402
    AtmosphereConfig,
    BlurConfig,
    CameraConfig,
    DetectionConfig,
    DisturbanceConfig,
    GaussianConfig,
    GimbalConfig,
    JitterConfig,
    LineMotion,
    PlatformConfig,
    PoissonConfig,
    SaltPepperConfig,
    SkyLockConfig,
    TargetConfig,
    TargetSetConfig,
    TrackingConfig,
)
from skylock.control.controller import PointingController  # noqa: E402
from skylock.core.pipeline import TrackingPipeline  # noqa: E402
from skylock.simulation.disturbances.base import DisturbanceContext  # noqa: E402
from skylock.simulation.gimbal import VirtualGimbal  # noqa: E402
from skylock.simulation.source import SimulationSource  # noqa: E402


def _build_all_disturbances_cfg() -> SkyLockConfig:
    """640×480 config with all disturbance types enabled at moderate/spec levels."""
    cam = CameraConfig(width=640, height=480, fov_h_deg=4.0, fov_v_deg=3.0, fps=30.0)
    target = TargetConfig(
        initial="fixed",
        initial_pos_deg=(2.0, 1.0),
        motion=LineMotion(speed_deg_s=0.5, heading_deg=0.0),
        size_px=10,
        brightness=220.0,
    )
    disturbances = DisturbanceConfig(
        salt_pepper=SaltPepperConfig(enabled=True, density=0.005),
        gaussian=GaussianConfig(enabled=True, sigma_levels=10.0),
        poisson=PoissonConfig(enabled=True, photon_scale=10.0),
        camera_jitter=JitterConfig(enabled=True, max_px_frame=10.0, correlation=0.5),
        platform=PlatformConfig(
            enabled=True, kind="linear",
            velocity_px_frame=3.0, max_px_frame=10.0,
        ),
        atmosphere=AtmosphereConfig(enabled=True, mode="haze", strength=0.2),
        blur=BlurConfig(enabled=True, sigma_px=1.0),
    )
    return SkyLockConfig(
        camera=cam,
        target=TargetSetConfig(count=1, targets=(target,)),
        gimbal=GimbalConfig(initial=(0.0, 0.0)),
        detection=DetectionConfig(),
        tracking=TrackingConfig(),
        disturbances=disturbances,
        seed=7,
    )


def _percentile(arr: list[float], p: float) -> float:
    if not arr:
        return 0.0
    return float(np.percentile(arr, p))


def _stats(arr: list[float]) -> dict:
    if not arr:
        return {"mean": None, "median": None, "p95": None, "max": None, "n": 0}
    a = np.array(arr)
    return {
        "mean": float(np.mean(a)),
        "median": float(np.median(a)),
        "p95": float(np.percentile(a, 95)),
        "max": float(np.max(a)),
        "n": len(arr),
    }


def run_measurement(n_frames: int, cfg: SkyLockConfig) -> dict:
    """Run one measurement pass over n_frames. Returns per-stage timing dicts."""
    gimbal = VirtualGimbal(cfg.gimbal)
    source = SimulationSource(cfg, gimbal=gimbal)
    source.open()

    pipeline = TrackingPipeline(cfg)
    controller = PointingController(
        cfg.control,
        cfg.camera,
        max_slew_rate_deg_s=cfg.gimbal.slew_rate_deg_s,
    )

    t_render: list[float] = []
    t_disturbance: list[float] = []
    t_detect: list[float] = []
    t_track: list[float] = []
    t_control: list[float] = []
    t_end_to_end: list[float] = []

    # Warm up: run 30 frames without recording
    for _ in range(min(30, n_frames // 10)):
        f = source.read()
        if f is None:
            break
        pipeline.process(f)

    source.reset()
    pipeline.reset()
    controller.reset()

    fps = cfg.camera.fps
    dt = 1.0 / fps

    # Measurement pass — time each stage separately
    # We re-implement the frame step here with fine-grained timing
    disturbance_stack = source.disturbances
    camera = source.camera
    target_set = source.target_set

    for frame_idx in range(n_frames):
        t_e2e_start = time.perf_counter()
        timestamp_s = frame_idx / fps
        current_pointing = gimbal.pointing

        # Stage: render
        t0 = time.perf_counter()
        dx, dy = disturbance_stack.compute_geometric_offset(frame_idx, timestamp_s)
        image_float, render_infos = camera.render(
            pointing=current_pointing,
            t=timestamp_s,
            targets=target_set.targets,
            extra_offset_px=(dx, dy),
        )
        t_render.append((time.perf_counter() - t0) * 1000.0)

        # Stage: disturbances
        t0 = time.perf_counter()
        ctx = DisturbanceContext(frame_index=frame_idx, timestamp_s=timestamp_s)
        image_disturbed = disturbance_stack.apply_photometric(image_float, ctx)
        image_uint8 = disturbance_stack.quantize(image_disturbed)
        t_disturbance.append((time.perf_counter() - t0) * 1000.0)

        # Build frame
        from skylock.core.types import Frame

        frame = Frame(
            image=image_uint8,
            index=frame_idx,
            timestamp_s=timestamp_s,
            source_id="perf_bench",
            pointing=current_pointing,
        )

        # Stage: detect
        t0 = time.perf_counter()
        h, w = frame.image.shape
        roi = pipeline.tracker.get_roi(width=w, height=h)
        detections = pipeline.detector.detect(frame, roi=roi)
        t_detect.append((time.perf_counter() - t0) * 1000.0)

        # Stage: track
        t0 = time.perf_counter()
        state, estimate, selected_candidate, intent = pipeline.tracker.step(frame, detections)
        t_track.append((time.perf_counter() - t0) * 1000.0)

        # Stage: control
        t0 = time.perf_counter()
        cmd = controller.step(
            intent=intent,
            estimate=estimate,
            pointing=current_pointing,
            dt=dt,
        )
        t_control.append((time.perf_counter() - t0) * 1000.0)

        # Apply gimbal
        gimbal.command(cmd, dt)

        t_e2e_end = time.perf_counter()
        t_end_to_end.append((t_e2e_end - t_e2e_start) * 1000.0)

    source.close()

    pipeline_latencies = [td + tt for td, tt in zip(t_detect, t_track, strict=True)]
    pipeline_fps = (n_frames / (sum(pipeline_latencies) / 1000.0)) if pipeline_latencies else 0.0
    e2e_fps = (n_frames / (sum(t_end_to_end) / 1000.0)) if t_end_to_end else 0.0

    return {
        "n_frames": n_frames,
        "pipeline_fps": pipeline_fps,
        "e2e_fps": e2e_fps,
        "render_ms": _stats(t_render),
        "disturbances_ms": _stats(t_disturbance),
        "detect_ms": _stats(t_detect),
        "track_ms": _stats(t_track),
        "control_ms": _stats(t_control),
        "pipeline_ms": _stats(pipeline_latencies),
        "end_to_end_ms": _stats(t_end_to_end),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SkyLock performance measurement script")
    parser.add_argument(
        "--frames", type=int, default=1000,
        help="Frames per repeat (default: 1000)",
    )
    parser.add_argument(
        "--repeats", type=int, default=3,
        help="Number of repeats (default: 3)",
    )
    parser.add_argument("--out", type=str, default="runs/perf", help="Output directory")
    args = parser.parse_args()

    n_frames: int = max(100, args.frames)
    n_repeats: int = max(1, args.repeats)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("SkyLock Performance Report")
    print(f"  Frames per repeat : {n_frames}")
    print(f"  Repeats           : {n_repeats}")
    print("  Resolution        : 640×480")
    print("  Disturbances      : ALL (moderate levels)")
    print()

    cfg = _build_all_disturbances_cfg()

    results = []
    for r in range(n_repeats):
        print(f"  Repeat {r + 1}/{n_repeats} ...", end=" ", flush=True)
        res = run_measurement(n_frames, cfg)
        results.append(res)
        print(
            f"pipeline_fps={res['pipeline_fps']:.1f}  "
            f"e2e_fps={res['e2e_fps']:.1f}  "
            f"detect_median={res['detect_ms']['median']:.2f} ms"
        )

    # Aggregate across repeats
    def _agg(key: str, stat: str) -> float | None:
        vals = [r[key][stat] for r in results if r[key].get(stat) is not None]
        return float(np.median(vals)) if vals else None

    def _stage_agg(key: str) -> dict:
        return {
            "median_ms": _agg(key, "median"),
            "p95_ms": _agg(key, "p95"),
            "mean_ms": _agg(key, "mean"),
        }

    pipeline_fps_vals = [r["pipeline_fps"] for r in results]
    e2e_fps_vals = [r["e2e_fps"] for r in results]

    report = {
        "run_id": str(uuid.uuid4()),
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "config": {
            "resolution": "640x480",
            "n_frames_per_repeat": n_frames,
            "n_repeats": n_repeats,
            "disturbances": "all_enabled_moderate",
        },
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python_version": sys.version,
            "numpy_version": np.__version__,
            "opencv_version": cv2.__version__,
        },
        "summary": {
            "pipeline_fps": {
                "median": float(np.median(pipeline_fps_vals)),
                "min": float(np.min(pipeline_fps_vals)),
                "max": float(np.max(pipeline_fps_vals)),
                "values": pipeline_fps_vals,
                "meets_20fps_spec": bool(np.median(pipeline_fps_vals) >= 20.0),
            },
            "e2e_fps": {
                "median": float(np.median(e2e_fps_vals)),
                "min": float(np.min(e2e_fps_vals)),
                "max": float(np.max(e2e_fps_vals)),
                "values": e2e_fps_vals,
            },
        },
        "per_stage_ms": {
            "render": _stage_agg("render_ms"),
            "disturbances": _stage_agg("disturbances_ms"),
            "detect": _stage_agg("detect_ms"),
            "track": _stage_agg("track_ms"),
            "control": _stage_agg("control_ms"),
            "pipeline_total": _stage_agg("pipeline_ms"),
            "end_to_end": _stage_agg("end_to_end_ms"),
        },
        "raw_repeats": results,
    }

    # Write JSON
    run_id_short = report["run_id"][:8]
    out_path = out_dir / f"perf_{run_id_short}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print("Summary")
    print(f"  Pipeline FPS (median): {report['summary']['pipeline_fps']['median']:.1f}")
    print(f"  E2E FPS      (median): {report['summary']['e2e_fps']['median']:.1f}")
    print(f"  Meets 20 FPS spec    : {report['summary']['pipeline_fps']['meets_20fps_spec']}")
    print()
    print("Per-stage latency (median ms across repeats):")
    for stage, stats in report["per_stage_ms"].items():
        med = stats.get("median_ms")
        p95 = stats.get("p95_ms")
        if med is not None:
            print(f"  {stage:<20} median={med:6.2f} ms  p95={p95:6.2f} ms")
    print()
    print(f"Report written to: {out_path}")

    # Exit non-zero if below 20 FPS requirement
    if not report["summary"]["pipeline_fps"]["meets_20fps_spec"]:
        print(
            f"WARNING: Pipeline FPS {report['summary']['pipeline_fps']['median']:.1f} "
            f"is below the 20 FPS specification requirement."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
