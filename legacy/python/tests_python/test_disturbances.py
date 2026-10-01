"""Tests for skylock.disturbances — Physical simulation noise."""

import numpy as np

from skylock.disturbances import DisturbanceManager


class TestDisturbanceManager:
    def test_preset_changes_params(self):
        dm = DisturbanceManager(preset="OFF")
        assert dm.get_params().noise_sigma == 0.0

        dm.set_preset("HIGH")
        assert dm.get_params().noise_sigma > 0.0
        assert dm.get_params().wander_rms_px > 0.0

    def test_deterministic_seed(self):
        dm1 = DisturbanceManager(seed=42, preset="HIGH")
        turb1 = dm1.get_turbulence(1.0)

        dm2 = DisturbanceManager(seed=42, preset="HIGH")
        turb2 = dm2.get_turbulence(1.0)

        assert turb1["wander_px"] == turb2["wander_px"]
        assert turb1["scintillation"] == turb2["scintillation"]

        dm3 = DisturbanceManager(seed=99, preset="HIGH")
        turb3 = dm3.get_turbulence(1.0)
        assert turb1["wander_px"] != turb3["wander_px"]

    def test_apply_sensor_stage_preserves_shape_and_type(self):
        dm = DisturbanceManager(preset="HIGH")

        # Create plain grey 10x10 frame
        frame = np.full((10, 10, 3), 128, dtype=np.uint8)

        out_frame = dm.apply_sensor_stage(frame)

        assert out_frame is not None
        assert out_frame.shape == (10, 10, 3)
        assert out_frame.dtype == np.uint8

        # Since noise is HIGH, some pixels should no longer be 128
        assert not np.all(out_frame == 128)

    def test_frame_drops(self):
        dm = DisturbanceManager(preset="HIGH")
        # HIGH preset has some drop probability
        drops = 0
        for _ in range(1000):
            if dm.should_drop_frame():
                drops += 1

        assert drops > 0
        assert dm.get_dropped_frames_count() == drops
