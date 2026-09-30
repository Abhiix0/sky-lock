"""Monochrome virtual camera with tangent-plane projection and sub-pixel splatting."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from skylock.config.models import CameraConfig
from skylock.core.geometry import angle_offset_to_pixel, angular_diff_deg
from skylock.core.types import Pointing
from skylock.simulation.targets import Target


@dataclass(frozen=True, slots=True)
class TargetRenderInfo:
    """True rendered target position and visibility state for a single frame."""

    px: float
    py: float
    visible: bool
    in_fov: bool
    target_id: str


class VirtualCamera:
    """Virtual camera model rendering monochrome sensor frames."""

    def __init__(self, config: CameraConfig) -> None:
        self.config = config

    def render(
        self,
        pointing: Pointing,
        t: float,
        targets: list[Target],
        extra_offset_px: tuple[float, float] = (0.0, 0.0),
    ) -> tuple[np.ndarray, list[TargetRenderInfo]]:
        """Render optical targets onto a 2-D float32 image array [0.0, 255.0].

        Returns:
            (image_float, target_render_infos)
        """
        width = self.config.width
        height = self.config.height

        # Initialize sensor plane with constant background level
        image = np.full((height, width), self.config.background_level, dtype=np.float32)
        render_infos: list[TargetRenderInfo] = []

        for target in targets:
            az_deg, el_deg = target.position(t)
            visible = target.is_visible(t)

            # Compute angular offset relative to camera pointing
            dpan = angular_diff_deg(az_deg, pointing.pan_deg)
            dtilt = angular_diff_deg(el_deg, pointing.tilt_deg)

            # Project to camera pixel space
            px_nom, py_nom = angle_offset_to_pixel(dpan, dtilt, self.config)
            px = px_nom + extra_offset_px[0]
            py = py_nom + extra_offset_px[1]

            in_fov = (0.0 <= px < width) and (0.0 <= py < height)
            render_infos.append(
                TargetRenderInfo(
                    px=px,
                    py=py,
                    visible=visible,
                    in_fov=in_fov,
                    target_id=target.spec.id,
                )
            )

            # Only splat onto sensor if target beacon is visible
            if not visible:
                continue

            sprite = target.sprite
            sh, sw = sprite.shape
            scx = (sw - 1.0) / 2.0
            scy = (sh - 1.0) / 2.0

            # Quick bounding box overlap test
            if (
                px + sw < 0
                or px - sw >= width
                or py + sh < 0
                or py - sh >= height
            ):
                continue

            # Bilinear sub-pixel splatting
            for r in range(sh):
                for c in range(sw):
                    s_val = float(sprite[r, c])
                    if s_val <= 0.0:
                        continue

                    val = target.brightness * s_val

                    # Continuous sensor location
                    xs = px + (c - scx)
                    ys = py + (r - scy)

                    x0 = int(math.floor(xs))
                    y0 = int(math.floor(ys))
                    fx = xs - x0
                    fy = ys - y0

                    # 4-pixel bilinear accumulation
                    w00 = (1.0 - fx) * (1.0 - fy)
                    w10 = fx * (1.0 - fy)
                    w01 = (1.0 - fx) * fy
                    w11 = fx * fy

                    if 0 <= y0 < height:
                        if 0 <= x0 < width:
                            image[y0, x0] = min(255.0, image[y0, x0] + val * w00)
                        if 0 <= x0 + 1 < width:
                            image[y0, x0 + 1] = min(255.0, image[y0, x0 + 1] + val * w10)

                    if 0 <= y0 + 1 < height:
                        if 0 <= x0 < width:
                            image[y0 + 1, x0] = min(255.0, image[y0 + 1, x0] + val * w01)
                        if 0 <= x0 + 1 < width:
                            image[y0 + 1, x0 + 1] = min(255.0, image[y0 + 1, x0 + 1] + val * w11)

        return image, render_infos
