"""Built-in benchmark scenario catalog.

All scenarios are returned by `builtin_scenarios()`, a function that creates a
fresh tuple on each call with no module-level mutable state.

Target offsets are chosen so acquisition <= 2 s is physically feasible:
- IFOV = 0.00625 deg/px (4 deg / 640 px)
- Slew rate = 5 deg/s  =>  2 s reach = 10 deg
- Default gimbal initial = (0, 0)
- FOV/2 = 2 deg horizontal, 1.5 deg vertical
- Target within ~5 deg => reachable in 1 s, leaving margin for detection and settling
"""

from __future__ import annotations

from skylock.benchmark.scenario import Scenario


def builtin_scenarios() -> tuple[Scenario, ...]:
    """Return all built-in benchmark scenarios as an immutable tuple.

    No module-level mutable state; each call produces a fresh tuple.
    """
    return (
        _s01_line_clean(),
        _s02_circle_clean(),
        _s03_fig8_clean(),
        _s04_random_clean(),
        _s05_line_spec_noise(),
        _s06_jitter20(),
        _s07_platform20(),
        _s08_haze(),
        _s09_fog(),
        _s10_rain(),
        _s11_low_light(),
        _s12_occlusion_reacq(),
        _s13_all_disturbances(),
        _s14_multi_target(),
        _s15_slew10(),
        _s16_mp4(),
    )


# ---------------------------------------------------------------------------
# Helper constants for target offsets
# ---------------------------------------------------------------------------
# All offsets are in degrees from gimbal initial (0,0).
# Feasibility: offset < slew_rate * acquisition_max_s = 5 * 2 = 10 deg
# Comfortable: offset ~2-5 deg => reach in 0.4-1.0 s
_DEFAULT_OFFSET = (2.0, 1.0)   # ~2.2 deg from boresight, reachable in <0.5 s
_CIRCLE_CENTER = (1.5, 0.5)     # circle center offset
_FIG8_CENTER = (1.0, 0.5)       # figure-8 center offset
_RANDOM_CENTER = (1.5, 0.5)     # random motion start near center


def _base_target(
    offset: tuple[float, float] = _DEFAULT_OFFSET,
    motion: dict | None = None,
    visibility_windows: list | None = None,
) -> dict:
    """Build a target config dict with sane defaults."""
    t: dict = {
        "id": "target_0",
        "size_px": 10,
        "shape": "disc",
        "brightness": 220.0,
        "initial": "fixed",
        "initial_pos_deg": list(offset),
        "motion": motion or {"kind": "line", "speed_deg_s": 0.5, "heading_deg": 0.0},
    }
    if visibility_windows:
        t["visibility_windows"] = visibility_windows
    return t


def _s01_line_clean() -> Scenario:
    return Scenario(
        id="S01_line_clean",
        description=(
            "Clean line motion, no disturbances. Target at (2.0, 1.0) deg offset, "
            "straight line at 0.5 deg/s heading 0. Acquisition feasible in <0.5 s at 5 deg/s slew."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target()],
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("clean", "line", "baseline"),
    )


def _s02_circle_clean() -> Scenario:
    return Scenario(
        id="S02_circle_clean",
        description=(
            "Clean circle motion, no disturbances. Target orbits (1.5, 0.5) deg at 1.0 deg radius "
            "with 10 s period. Acquisition feasible in <0.5 s."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target(
                offset=_CIRCLE_CENTER,
                motion={"kind": "circle", "radius_deg": 1.0, "period_s": 10.0, "phase_rad": 0.0},
            )],
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("clean", "circle"),
    )


def _s03_fig8_clean() -> Scenario:
    return Scenario(
        id="S03_fig8_clean",
        description=(
            "Clean figure-8 motion, no disturbances. Target traces figure-8 around (1.0, 0.5) deg, "
            "1.5 deg width, 1.0 deg height, 12 s period. Acquisition feasible in <0.3 s."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target(
                offset=_FIG8_CENTER,
                motion={"kind": "figure8", "width_deg": 1.5, "height_deg": 1.0, "period_s": 12.0},
            )],
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("clean", "figure8"),
    )


def _s04_random_clean() -> Scenario:
    return Scenario(
        id="S04_random_clean",
        description=(
            "Clean random walk motion, no disturbances. Target starts at (1.5, 0.5) deg, "
            "random walk at 0.5 deg/s with 2 s correlation. Acquisition feasible in <0.5 s."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target(
                offset=_RANDOM_CENTER,
                motion={
                    "kind": "random",
                    "speed_deg_s": 0.5,
                    "correlation_s": 2.0,
                    "bounds_deg": [-1.5, 1.5, -1.0, 1.0],
                },
            )],
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("clean", "random"),
    )


def _s05_line_spec_noise() -> Scenario:
    return Scenario(
        id="S05_line_spec_noise",
        description=(
            "Line motion with PS_SPEC maximum noise: gaussian sigma=20, "
            "salt & pepper density=0.01, Poisson photon_scale=10. "
            "Target at (2.0, 1.0) deg. Tests detection robustness."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target()],
            "disturbances.gaussian.enabled": True,
            "disturbances.gaussian.sigma_levels": 20.0,
            "disturbances.salt_pepper.enabled": True,
            "disturbances.salt_pepper.density": 0.01,
            "disturbances.poisson.enabled": True,
            "disturbances.poisson.photon_scale": 10.0,
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("noisy", "line", "spec"),
    )


def _s06_jitter20() -> Scenario:
    return Scenario(
        id="S06_jitter20",
        description=(
            "Line motion with camera jitter at ±20 px/frame (PS_SPEC max). "
            "Target at (2.0, 1.0) deg. Tests jitter rejection."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target()],
            "disturbances.camera_jitter.enabled": True,
            "disturbances.camera_jitter.max_px_frame": 20.0,
            "disturbances.camera_jitter.correlation": 0.5,
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("jitter", "line"),
    )


def _s07_platform20() -> Scenario:
    return Scenario(
        id="S07_platform20",
        description=(
            "Line motion with platform drift at 20 px/frame (PS_SPEC max). "
            "Target at (2.0, 1.0) deg. Tests platform motion compensation."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target()],
            "disturbances.platform.enabled": True,
            "disturbances.platform.kind": "linear",
            "disturbances.platform.max_px_frame": 20.0,
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("platform", "line"),
    )


def _s08_haze() -> Scenario:
    return Scenario(
        id="S08_haze",
        description=(
            "Line motion with haze atmosphere (strength=0.3). "
            "Target at (2.0, 1.0) deg. Tests detection in reduced contrast."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target()],
            "disturbances.atmosphere.enabled": True,
            "disturbances.atmosphere.mode": "haze",
            "disturbances.atmosphere.strength": 0.3,
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("atmosphere", "haze", "line"),
    )


def _s09_fog() -> Scenario:
    return Scenario(
        id="S09_fog",
        description=(
            "Line motion with fog atmosphere (strength=0.5). "
            "Target at (2.0, 1.0) deg. Tests detection in heavy degradation."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target()],
            "disturbances.atmosphere.enabled": True,
            "disturbances.atmosphere.mode": "fog",
            "disturbances.atmosphere.strength": 0.5,
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("atmosphere", "fog", "line"),
    )


def _s10_rain() -> Scenario:
    return Scenario(
        id="S10_rain",
        description=(
            "Line motion with rain atmosphere (strength=0.4). "
            "Target at (2.0, 1.0) deg. Tests detection in rain streaks."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target()],
            "disturbances.atmosphere.enabled": True,
            "disturbances.atmosphere.mode": "rain",
            "disturbances.atmosphere.strength": 0.4,
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("atmosphere", "rain", "line"),
    )


def _s11_low_light() -> Scenario:
    return Scenario(
        id="S11_low_light",
        description=(
            "Line motion with low-light conditions: reduced target brightness=80, "
            "background_level=5, Poisson photon_scale=5. Target at (2.0, 1.0) deg."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target(offset=_DEFAULT_OFFSET)],
            "camera.background_level": 5.0,
            "disturbances.poisson.enabled": True,
            "disturbances.poisson.photon_scale": 5.0,
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("low_light", "line"),
    )


def _s12_occlusion_reacq() -> Scenario:
    return Scenario(
        id="S12_occlusion_reacq",
        description=(
            "Line motion with a 0.5 s occlusion window at t=2.5-3.0 s. "
            "Target occluded during [2.5, 3.0] s; visible all other times. "
            "Target at (2.0, 1.0) deg. Tests LOST→REACQUIRE→TRACK cycle. "
            "NOTE (bug-fix): visibility_windows are OCCLUSION windows in the simulation "
            "code (target hidden while inside the window). "
            "Tests reacquisition within 1.0 s timeout."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target(
                visibility_windows=[[2.5, 3.0]],  # Single occlusion gap: hidden 2.5–3.0 s
            )],
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("occlusion", "reacquisition", "line"),
    )


def _s13_all_disturbances() -> Scenario:
    return Scenario(
        id="S13_all_disturbances",
        description=(
            "Line motion with ALL disturbances active at moderate levels: "
            "gaussian sigma=10, S&P 0.005, Poisson scale=10, jitter 10 px, "
            "platform 5 px, haze 0.2, blur 1.0 px. Target at (2.0, 1.0) deg."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target()],
            "disturbances.gaussian.enabled": True,
            "disturbances.gaussian.sigma_levels": 10.0,
            "disturbances.salt_pepper.enabled": True,
            "disturbances.salt_pepper.density": 0.005,
            "disturbances.poisson.enabled": True,
            "disturbances.poisson.photon_scale": 10.0,
            "disturbances.camera_jitter.enabled": True,
            "disturbances.camera_jitter.max_px_frame": 10.0,
            "disturbances.camera_jitter.correlation": 0.5,
            "disturbances.platform.enabled": True,
            "disturbances.platform.kind": "linear",
            "disturbances.platform.max_px_frame": 5.0,
            "disturbances.atmosphere.enabled": True,
            "disturbances.atmosphere.mode": "haze",
            "disturbances.atmosphere.strength": 0.2,
            "disturbances.blur.enabled": True,
            "disturbances.blur.sigma_px": 1.0,
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("all_disturbances", "stress", "line"),
    )


def _s14_multi_target() -> Scenario:
    return Scenario(
        id="S14_multi_target",
        description=(
            "Two targets: primary at (2.0, 1.0) deg line, secondary at (3.0, -1.0) deg circle. "
            "Tests multi-target discrimination. No disturbances."
        ),
        overrides={
            "target.count": 2,
            "target.targets": [
                _base_target(offset=_DEFAULT_OFFSET),
                {
                    "id": "target_1",
                    "size_px": 8,
                    "shape": "disc",
                    "brightness": 180.0,
                    "initial": "fixed",
                    "initial_pos_deg": [3.0, -1.0],
                    "motion": {
                        "kind": "circle",
                        "radius_deg": 0.5,
                        "period_s": 8.0,
                        "phase_rad": 0.0,
                    },
                },
            ],
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("multi_target", "clean"),
    )


def _s15_slew10() -> Scenario:
    return Scenario(
        id="S15_slew10",
        description=(
            "Line motion, max slew rate = 10 deg/s. "
            "Target at (5.0, 3.0) deg offset (reachable in ~0.6 s at 10 deg/s). "
            "Tests higher slew rate tracking."
        ),
        overrides={
            "target.count": 1,
            "target.targets": [_base_target(offset=(5.0, 3.0))],
            "gimbal.slew_rate_deg_s": 10.0,
        },
        duration_s=6.0,
        seeds=(42,),
        tags=("slew", "line"),
    )


def _s16_mp4() -> Scenario:
    return Scenario(
        id="S16_mp4",
        description=(
            "MP4 video input. Path supplied at runtime via mp4_path override. "
            "If no MP4 is provided, produces a NOT_RUN record (not a crash)."
        ),
        overrides={},
        duration_s=0.0,  # Duration determined by video length
        seeds=(1,),
        input_kind="mp4",
        mp4_path=None,  # Must be set at runtime
        tags=("mp4", "video"),
    )


__all__ = ("builtin_scenarios",)
