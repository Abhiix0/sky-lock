"""Simulation frame source implementing the FrameSource protocol."""

from __future__ import annotations

from skylock.config.models import SkyLockConfig
from skylock.core.enums import InputKind
from skylock.core.interfaces import FrameSource, GimbalPlant
from skylock.core.types import ControlCommand, Frame, GroundTruthSample, Pointing
from skylock.simulation.camera import VirtualCamera
from skylock.simulation.disturbances.base import DisturbanceContext
from skylock.simulation.disturbances.stack import DisturbanceStack
from skylock.simulation.gimbal import VirtualGimbal
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
        self.gimbal = gimbal if gimbal is not None else VirtualGimbal(config.gimbal)
        self.camera = VirtualCamera(config.camera)
        
        # Compute screen bounds in degrees for target motion
        px_per_deg = config.camera.px_per_deg
        screen_bounds_deg = config.screen.world_extent_deg(px_per_deg)
        
        self.target_set = TargetSet(
            config.target,
            seed=config.seed,
            screen_bounds_deg=screen_bounds_deg,
        )
        self.disturbances = DisturbanceStack(
            config=config.disturbances,
            seed=config.seed,
            background_level=config.camera.background_level,
        )
        self._frame_index = 0
        self._is_open = True

    def open(self) -> None:
        self._is_open = True

    def _render_frame(self) -> tuple[Frame, GroundTruthSample]:
        fps = self.config.camera.fps
        timestamp_s = self._frame_index / fps
        current_pointing = self.gimbal.pointing

        # 1. Compute line-of-sight shift from geometric disturbances
        dx, dy = self.disturbances.compute_geometric_offset(self._frame_index, timestamp_s)

        # 2. Render targets with geometric shift passed to camera (so target positions reflect it)
        image_float, render_infos = self.camera.render(
            pointing=current_pointing,
            t=timestamp_s,
            targets=self.target_set.targets,
            extra_offset_px=(dx, dy),
        )

        # 3. Apply photometric disturbances in strict order
        ctx = DisturbanceContext(frame_index=self._frame_index, timestamp_s=timestamp_s)
        image_disturbed = self.disturbances.apply_photometric(image_float, ctx)

        # 4. Quantize to 8-bit monochrome
        image_uint8 = self.disturbances.quantize(image_disturbed)

        # Build Frame (STRICTLY NO GROUND TRUTH)
        frame = Frame(
            image=image_uint8,
            index=self._frame_index,
            timestamp_s=timestamp_s,
            source_id=self.source_id,
            pointing=current_pointing,
        )

        # Ground truth records the applied (dx, dy) offset and post-disturbance true pixel
        gt = build_ground_truth(
            frame_index=self._frame_index,
            timestamp_s=timestamp_s,
            render_infos=render_infos,
            targets=self.target_set.targets,
            pointing=current_pointing,
            camera=self.config.camera,
            disturbance_offset_px=(dx, dy),
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
        self.disturbances.reset()

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
