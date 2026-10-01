"""Integration test connecting SimulationSource directly to ClassicalBlobDetector."""

import math

from skylock.config.models import (
    AtmosphereConfig,
    DetectionConfig,
    DisturbanceConfig,
    GaussianConfig,
    PoissonConfig,
    SaltPepperConfig,
    SkyLockConfig,
)
from skylock.config.presets import preset_low_light, preset_rain
from skylock.simulation.source import SimulationSource
from skylock.vision.detector import ClassicalBlobDetector


def _evaluate_scenario(
    dist_cfg: DisturbanceConfig,
    frames: int = 100,
    seed: int = 42,
) -> tuple[float, float]:
    """Evaluate detector against SimulationSource using GroundTruth strictly within the test.

    Returns:
        (detection_rate_pct, false_positives_per_frame)
    """
    from skylock.config.io import from_dict
    
    # Use fixed target position within FOV to ensure it's always visible
    cfg = from_dict({
        "seed": seed,
        "disturbances": dist_cfg,
        "target": {
            "targets": [{
                "id": "target_0",
                "size_px": 10,
                "shape": "square",
                "brightness": 220.0,
                "initial": "fixed",
                "initial_pos_deg": [0.5, 0.5],  # Well within FOV
                "motion": {"kind": "line", "speed_deg_s": 0.5, "heading_deg": 0.0},
            }]
        },
    })
    source = SimulationSource(cfg)
    detector = ClassicalBlobDetector(DetectionConfig())

    hits = 0
    observable_frames = 0
    false_positives = 0

    for _ in range(frames):
        frame, gt = source.read_with_truth()
        detections = detector.detect(frame)

        if gt.primary_visible and gt.primary_px is not None:
            observable_frames += 1
            tx, ty = gt.primary_px
            target_matched = False

            for det in detections:
                dist = math.hypot(det.cx - tx, det.cy - ty)
                if dist <= 12.0:
                    target_matched = True
                else:
                    false_positives += 1

            if target_matched:
                hits += 1
        else:
            # If target is not visible, any detection is a false positive
            false_positives += len(detections)

    detection_rate = (hits / observable_frames * 100.0) if observable_frames > 0 else 0.0
    fp_per_frame = false_positives / frames
    return detection_rate, fp_per_frame


def test_detector_under_maximum_sensor_noise_300_frames() -> None:
    """300 seeded frames with Gaussian sigma=20 + S&P 2% + Poisson.

    Acceptance: detection_rate >= 95% and false_positives <= 0.1 / frame.
    """
    max_noise_cfg = DisturbanceConfig(
        gaussian=GaussianConfig(enabled=True, sigma_levels=20.0),
        salt_pepper=SaltPepperConfig(enabled=True, density=0.02),
        poisson=PoissonConfig(enabled=True, photon_scale=1.0),
    )

    det_rate, fp_rate = _evaluate_scenario(max_noise_cfg, frames=300, seed=12345)
    print(
        f"\n[INTEGRATION] Max Noise (G20+SP2%+P): "
        f"Detection Rate = {det_rate:.2f}%, FP/frame = {fp_rate:.3f}"
    )

    assert det_rate >= 95.0, f"Detection rate {det_rate:.2f}% fell below 95%"
    assert fp_rate <= 0.1, f"False positive rate {fp_rate:.3f}/frame exceeded 0.1"


def test_detector_atmospheric_scenarios() -> None:
    """Evaluate detector under haze, fog, rain, and low-light presets."""
    scenarios = {
        "Haze": DisturbanceConfig(
            atmosphere=AtmosphereConfig(enabled=True, mode="haze", strength=0.5),
        ),
        "Fog": DisturbanceConfig(
            atmosphere=AtmosphereConfig(enabled=True, mode="fog", strength=0.5),
        ),
        "Rain": preset_rain(),
        "Low-Light": preset_low_light(),
    }

    for name, cfg in scenarios.items():
        det_rate, fp_rate = _evaluate_scenario(cfg, frames=60, seed=999)
        print(f"\n[INTEGRATION] {name}: Detection Rate = {det_rate:.2f}%, FP/frame = {fp_rate:.3f}")
