"""Simulation frame source implementing the FrameSource protocol."""

from __future__ import annotations

import numpy as np

from skylock.config.models import SkyLockConfig
from skylock.core.enums import InputKind
from skylock.core.interfaces import FrameSource, GimbalPlant
from skylock.core.types import ControlCommand, Frame, GroundTruthSample, Pointing
from skylock.simulation.camera import VirtualCamera
from skylock.simulation.ground_truth import build_ground_truth
from skylock.simulation.targets import TargetSet


class FixedPointingGimbal:
    """Fixed-pointing gimbal plant that does not move (for open-loop testing)."""

    def __init__(self, initial_pointing: Pointing | None = None) -> None:
        init = initial_pointing if initial_pointing is not None else Pointing(0.0, 0.0)
        self._initial = init
        self._pointing = init

    def command(self, cmd: ControlCommand, dt: float) -> None:
        pass

    @property
    def pointing(self) -> Pointing:
        return self._pointing

    def reset(self) -> None:
        self._pointing = self._initial


class SimulationSource(FrameSource):
    """Deterministic simulation frame source producing synthetic monochrome sensor frames."""

    def __init__(
        self,
        config: SkyLockConfig,
        gimbal: GimbalPlant | None = None,
    ) -> None:
        self.config = config
        init_pointing = Pointing(
            pan_deg=config.gimbal.initial[0],
            tilt_deg=config.gimbal.initial[1],
        )
        self.gimbal = gimbal if gimbal is not None else FixedPointingGimbal(init_pointing)
        self.camera = VirtualCamera(config.camera)
        self.target_set = TargetSet(config.target, seed=config.seed)
        self._frame_index = 0
        self._is_open = True

    def open(self) -> None:
        self._is_open = True

    def _render_frame(self) -> tuple[Frame, GroundTruthSample]:
        fps = self.config.camera.fps
        timestamp_s = self._frame_index / fps
        current_pointing = self.gimbal.pointing

        image_float, render_infos = self.camera.render(
            pointing=current_pointing,
            t=timestamp_s,
            targets=self.target_set.targets,
        )

        # Quantize to 8-bit monochrome
        image_uint8 = np.clip(np.round(image_float), 0, 255).astype(np.uint8)

        # Build Frame (STRICTLY NO GROUND TRUTH)
        frame = Frame(
            image=image_uint8,
            index=self._frame_index,
            timestamp_s=timestamp_s,
            source_id=self.source_id,
            pointing=current_pointing,
        )

        gt = build_ground_truth(
            frame_index=self._frame_index,
            timestamp_s=timestamp_s,
            render_infos=render_infos,
            targets=self.target_set.targets,
            pointing=current_pointing,
            camera=self.config.camera,
        )

        self._frame_index += 1
        return frame, gt

    def read(self) -> Frame | None:
        if not self._is_open:
            return None
        frame, _ = self._render_frame()
        return frame

    def read_with_truth(self) -> tuple[Frame, GroundTruthSample]:
        if not self._is_open:
            raise RuntimeError("SimulationSource is closed")
        return self._render_frame()

    def reset(self) -> None:
        self._frame_index = 0
        self.target_set.reset()
        self.gimbal.reset()

    def close(self) -> None:
        self._is_open = False

    @property
    def width(self) -> int:
        return self.config.camera.width

    @property
    def height(self) -> int:
        return self.config.camera.height

    @property
    def fps(self) -> float:
        return self.config.camera.fps

    @property
    def source_id(self) -> str:
        return "simulation"

    @property
    def kind(self) -> InputKind:
        return InputKind.SIMULATION
