"""
Disturbances module.

Applies deterministic physical disturbances to the simulation environment:
- Atmospheric wander (Ornstein-Uhlenbeck)
- Scintillation (Log-normal)
- Platform vibration / jitter (Ornstein-Uhlenbeck)
- Sensor read noise (Gaussian)
- Hot pixels
- Defocus blur
- Frame drops

JS reference: src/tracking/disturbances.js
"""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

from skylock.config import DISTURBANCE_PRESETS, DisturbanceConfig


class DisturbanceManager:
    """Manages physical disturbances and sensor noise."""

    def __init__(self, seed: int = 12345, preset: str = "OFF") -> None:
        self._seed = seed
        self._preset = preset.upper()
        if self._preset not in DISTURBANCE_PRESETS:
            self._preset = "OFF"

        # Copy preset config
        base = DISTURBANCE_PRESETS[self._preset]
        self._params = DisturbanceConfig(
            wander_rms_px=base.wander_rms_px,
            wander_corner_hz=base.wander_corner_hz,
            scintillation_sigma=base.scintillation_sigma,
            jitter_rms_deg=base.jitter_rms_deg,
            vibration_hz=base.vibration_hz,
            noise_sigma=base.noise_sigma,
            hot_pixels_count=base.hot_pixels_count,
            blur_radius_px=base.blur_radius_px,
            drop_probability=base.drop_probability,
        )

        self._turb_rng = np.random.default_rng()
        self._vib_rng = np.random.default_rng()
        self._sens_rng = np.random.default_rng()
        self._drop_rng = np.random.default_rng()

        self._wander_x = 0.0
        self._wander_y = 0.0
        self._scint_state = 0.0
        self._last_turb_time: float | None = None

        self._jitter_pan = 0.0
        self._jitter_tilt = 0.0
        self._last_vib_time: float | None = None

        self._dropped_frames_count = 0
        self._hot_pixels: list[tuple[int, int]] = []

        self.set_seed(seed)

    def set_seed(self, seed: int) -> None:
        """Reinitialize PRNG streams deterministically."""
        self._seed = seed

        # Derive streams
        s_turb = (seed ^ 0x9E3779B9) & 0xFFFFFFFF
        s_vib = (seed ^ 0x6A09E667) & 0xFFFFFFFF
        s_sens = (seed ^ 0xBB67AE85) & 0xFFFFFFFF
        s_drop = (seed ^ 0x3C6EF372) & 0xFFFFFFFF

        self._turb_rng = np.random.default_rng(s_turb)
        self._vib_rng = np.random.default_rng(s_vib)
        self._sens_rng = np.random.default_rng(s_sens)
        self._drop_rng = np.random.default_rng(s_drop)

        self._wander_x = 0.0
        self._wander_y = 0.0
        self._scint_state = 0.0
        self._last_turb_time = None

        self._jitter_pan = 0.0
        self._jitter_tilt = 0.0
        self._last_vib_time = None

        self._dropped_frames_count = 0
        self._regenerate_hot_pixels(640, 480)

    def set_preset(self, name: str) -> None:
        """Set disturbance preset by name."""
        name = name.upper()
        if name in DISTURBANCE_PRESETS:
            self._preset = name
            base = DISTURBANCE_PRESETS[name]
            self._params = DisturbanceConfig(
                wander_rms_px=base.wander_rms_px,
                wander_corner_hz=base.wander_corner_hz,
                scintillation_sigma=base.scintillation_sigma,
                jitter_rms_deg=base.jitter_rms_deg,
                vibration_hz=base.vibration_hz,
                noise_sigma=base.noise_sigma,
                hot_pixels_count=base.hot_pixels_count,
                blur_radius_px=base.blur_radius_px,
                drop_probability=base.drop_probability,
            )
            self._regenerate_hot_pixels(640, 480)

    def get_params(self) -> DisturbanceConfig:
        return self._params

    def _regenerate_hot_pixels(self, w: int, h: int) -> None:
        self._hot_pixels = []
        count = self._params.hot_pixels_count
        if count <= 0:
            return

        for _ in range(count):
            x = int(self._sens_rng.integers(0, w))
            y = int(self._sens_rng.integers(0, h))
            self._hot_pixels.append((x, y))

    def get_turbulence(self, sim_time_sec: float) -> dict[str, Any]:
        """Step atmospheric turbulence OU processes."""
        if self._params.wander_rms_px == 0 and self._params.scintillation_sigma == 0:
            self._wander_x = 0.0
            self._wander_y = 0.0
            self._scint_state = 0.0
            self._last_turb_time = sim_time_sec
            return {"wander_px": (0.0, 0.0), "scintillation": 1.0}

        if self._last_turb_time is None:
            self._last_turb_time = sim_time_sec
            self._wander_x = float(self._turb_rng.normal(0, self._params.wander_rms_px))
            self._wander_y = float(self._turb_rng.normal(0, self._params.wander_rms_px))
            self._scint_state = float(self._turb_rng.normal(0, self._params.scintillation_sigma))
        else:
            dt = max(0.0, sim_time_sec - self._last_turb_time)
            self._last_turb_time = sim_time_sec

            if dt > 0:
                # Ornstein-Uhlenbeck decay
                omega_wander = 2.0 * math.pi * self._params.wander_corner_hz
                alpha_w = math.exp(-omega_wander * dt)
                sigma_w = self._params.wander_rms_px * math.sqrt(max(0.0, 1.0 - alpha_w**2))

                self._wander_x = alpha_w * self._wander_x + float(self._turb_rng.normal(0, sigma_w))
                self._wander_y = alpha_w * self._wander_y + float(self._turb_rng.normal(0, sigma_w))

                omega_scint = 2.0 * math.pi * 4.0
                alpha_s = math.exp(-omega_scint * dt)
                sigma_s = self._params.scintillation_sigma * math.sqrt(max(0.0, 1.0 - alpha_s**2))

                self._scint_state = alpha_s * self._scint_state + float(
                    self._turb_rng.normal(0, sigma_s)
                )

        # Log-normal intensity multiplier
        mean_correction = -0.5 * self._params.scintillation_sigma**2
        scintillation = math.exp(mean_correction + self._scint_state)
        scintillation = max(0.01, min(4.0, scintillation))

        return {
            "wander_px": (self._wander_x, self._wander_y),
            "scintillation": scintillation,
        }

    def get_vibration(self, sim_time_sec: float) -> dict[str, float]:
        """Step platform vibration angular jitter."""
        if self._params.jitter_rms_deg == 0:
            self._jitter_pan = 0.0
            self._jitter_tilt = 0.0
            self._last_vib_time = sim_time_sec
            return {"pan_jitter_deg": 0.0, "tilt_jitter_deg": 0.0}

        if self._last_vib_time is None:
            self._last_vib_time = sim_time_sec
            self._jitter_pan = float(self._vib_rng.normal(0, self._params.jitter_rms_deg))
            self._jitter_tilt = float(self._vib_rng.normal(0, self._params.jitter_rms_deg))
        else:
            dt = max(0.0, sim_time_sec - self._last_vib_time)
            self._last_vib_time = sim_time_sec

            if dt > 0:
                omega_vib = 2.0 * math.pi * self._params.vibration_hz
                alpha_v = math.exp(-omega_vib * dt)
                sigma_v = self._params.jitter_rms_deg * math.sqrt(max(0.0, 1.0 - alpha_v**2))

                self._jitter_pan = alpha_v * self._jitter_pan + float(
                    self._vib_rng.normal(0, sigma_v)
                )
                self._jitter_tilt = alpha_v * self._jitter_tilt + float(
                    self._vib_rng.normal(0, sigma_v)
                )

        return {
            "pan_jitter_deg": self._jitter_pan,
            "tilt_jitter_deg": self._jitter_tilt,
        }

    def should_drop_frame(self) -> bool:
        """Check if frame drops."""
        if self._params.drop_probability <= 0:
            return False

        dropped = self._drop_rng.random() < self._params.drop_probability
        if dropped:
            self._dropped_frames_count += 1
        return dropped

    def get_dropped_frames_count(self) -> int:
        return self._dropped_frames_count

    def apply_sensor_stage(self, frame: np.ndarray | None) -> np.ndarray | None:
        """Apply noise, hot pixels, and blur to a BGR frame (in-place modification).

        Args:
            frame: Numpy BGR image array.
        Returns:
            The modified frame.
        """
        if frame is None or frame.size == 0:
            return frame

        has_noise = self._params.noise_sigma > 0
        has_hot = self._params.hot_pixels_count > 0 and len(self._hot_pixels) > 0
        has_blur = self._params.blur_radius_px > 0

        if not has_noise and not has_hot and not has_blur:
            return frame

        h, w = frame.shape[:2]

        # 1. Noise
        if has_noise:
            # Generate noise
            noise = self._sens_rng.normal(0, self._params.noise_sigma, frame.shape)
            noisy_frame = frame.astype(np.float32) + noise
            np.clip(noisy_frame, 0, 255, out=noisy_frame)
            frame[:] = noisy_frame.astype(np.uint8)

        # 2. Hot pixels
        if has_hot:
            for px, py in self._hot_pixels:
                if 0 <= py < h and 0 <= px < w:
                    frame[py, px] = [255, 255, 255]

        # 3. Blur
        if has_blur:
            r = int(self._params.blur_radius_px)
            ksize = 2 * r + 1
            cv2.blur(frame, (ksize, ksize), dst=frame)

        return frame

    def reset(self) -> None:
        """Reset to initial seed."""
        self.set_seed(self._seed)
