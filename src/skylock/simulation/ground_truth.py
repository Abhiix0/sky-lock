"""Ground truth telemetry generator for simulation metrics and evaluation."""

from __future__ import annotations

import math

from skylock.config.models import CameraConfig
from skylock.core.types import GroundTruthSample, Pointing, TargetTruth
from skylock.simulation.camera import TargetRenderInfo
from skylock.simulation.targets import Target


def build_ground_truth(
    frame_index: int,
    timestamp_s: float,
    render_infos: list[TargetRenderInfo],
    targets: list[Target],
    pointing: Pointing,
    camera: CameraConfig,
) -> GroundTruthSample:
    """Construct a GroundTruthSample for evaluation.

    METRICS ONLY — never deliver to tracking or vision algorithms.
    """
    target_truths: list[TargetTruth] = []

    for info, target in zip(render_infos, targets, strict=True):
        az_deg, el_deg = target.position(timestamp_s)
        truth = TargetTruth(
            id=info.target_id,
            az_deg=az_deg,
            el_deg=el_deg,
            px=info.px,
            py=info.py,
            visible=info.visible,
            in_fov=info.in_fov,
        )
        target_truths.append(truth)

    primary_px: tuple[float, float] | None = None
    primary_visible = False
    boresight_error_px: float | None = None

    if render_infos:
        prim_info = render_infos[0]
        # Primary is observable if it is both unoccluded (visible) and within camera FOV
        if prim_info.visible and prim_info.in_fov:
            primary_visible = True
            primary_px = (prim_info.px, prim_info.py)

            cx = (camera.width - 1.0) / 2.0
            cy = (camera.height - 1.0) / 2.0
            boresight_error_px = float(math.hypot(prim_info.px - cx, prim_info.py - cy))

    return GroundTruthSample(
        frame_index=frame_index,
        timestamp_s=timestamp_s,
        targets=tuple(target_truths),
        primary_px=primary_px,
        primary_visible=primary_visible,
        boresight_error_px=boresight_error_px,
        pointing=pointing,
    )
