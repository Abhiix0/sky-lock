"""
FSOC acquisition and tracking state machine.

States:
- SEARCH: Sweeping space with raster pattern looking for beacon.
- ACQUIRE: Centering candidate and confirming across multiple frames.
- TRACK: Closed-loop Kalman-filtered line-of-sight tracking.
- LOST: Coastal propagation on Kalman dynamics during signal occlusion.
- REACQUIRE: Expanding Archimedean spiral search around predicted LOS.

JS reference: src/tracking/stateMachine.js
"""

from __future__ import annotations

from typing import Any

from skylock.config import CAMERA, KALMAN, TRACKING, CameraConfig, TrackingConfig
from skylock.geometry import pixel_to_body_angles
from skylock.kalman import KalmanFilter
from skylock.scan_patterns import raster, spiral


class StateMachine:
    """State machine for tracking modes."""

    def __init__(self, config: TrackingConfig = TRACKING) -> None:
        self._cfg = config

        self.state: str = "SEARCH"
        self._state_start_time: float = 0.0
        self._last_seen_time: float = 0.0

        self._candidate_pan_deg: float = 0.0
        self._candidate_tilt_deg: float = 0.0
        self._candidate_confirm_count: int = 0

        self._consecutive_misses: int = 0
        self._spiral_center: dict[str, float] = {"pan_deg": 0.0, "tilt_deg": 0.0}

        self._event_log: list[dict[str, Any]] = []

    def _transition_to(self, next_state: str, sim_time: float, reason: str) -> None:
        """Internal state transition."""
        if next_state == self.state:
            return

        event = {
            "type": "STATE_CHANGE",
            "from": self.state,
            "to": next_state,
            "sim_time": sim_time,
            "reason": reason,
        }
        self._event_log.append(event)

        self.state = next_state
        self._state_start_time = sim_time

        if next_state == "ACQUIRE":
            self._candidate_confirm_count = 1
            self._last_seen_time = sim_time
        elif next_state == "TRACK":
            self._consecutive_misses = 0
            self._last_seen_time = sim_time
        elif next_state == "LOST":
            self._consecutive_misses = 0

    def update(
        self,
        sim_time: float,
        detections: list[dict[str, Any]],
        gimbal_state: dict[str, Any],
        kalman: KalmanFilter | None = None,
        camera: CameraConfig = CAMERA,
        confirmed_candidate: dict[str, Any] | None = None,
        strongest_candidate: dict[str, Any] | None = None,
        all_candidates: bool = False,
    ) -> dict[str, Any]:
        """Process a detection frame update and determine next control target and state.

        Args:
            sim_time: Simulation time in seconds.
            detections: Detected blobs from detector.
            gimbal_state: Current gimbal telemetry.
            kalman: Kalman filter instance (optional).
            camera: Camera configuration.
            confirmed_candidate: Optional blink ID confirmed candidate.
            strongest_candidate: Optional strongest blink ID candidate.
            all_candidates: Whether candidate tracker is active.

        Returns:
            Dict containing state, mode, setpoint, selected_detection, events.
        """
        emitted_events = []
        min_snr = self._cfg.min_snr_search
        gate_sigma = KALMAN.gate_threshold_sigma

        selected_detection = None
        mode = "GOTO"

        gimbal_pan = float(gimbal_state.get("pan_deg", 0.0))
        gimbal_tilt = float(gimbal_state.get("tilt_deg", 0.0))

        setpoint = {"pan_deg": gimbal_pan, "tilt_deg": gimbal_tilt}

        # Find best candidate detection with highest peak/SNR
        best_detection = None
        if detections:
            for d in detections:
                if d["snr"] >= min_snr:
                    best_detection = d
                    break
            if not best_detection:
                best_detection = detections[0]

        if self.state == "SEARCH":
            scan = raster(sim_time - self._state_start_time, self._cfg, camera)
            setpoint = {"pan_deg": scan["pan_deg"], "tilt_deg": scan["tilt_deg"]}
            mode = "GOTO"

            if best_detection and best_detection["snr"] >= min_snr:
                selected_detection = best_detection
                pan, tilt = pixel_to_body_angles(
                    best_detection["cx"],
                    best_detection["cy"],
                    gimbal_pan,
                    gimbal_tilt,
                    camera,
                )
                self._candidate_pan_deg = pan
                self._candidate_tilt_deg = tilt
                self._transition_to("ACQUIRE", sim_time, "Detection above SNR gate in SEARCH")
                emitted_events.append(self._event_log[-1])

        elif self.state == "ACQUIRE":
            mode = "GOTO"

            active_target = confirmed_candidate or strongest_candidate or best_detection

            if active_target:
                cx = active_target.get("x", active_target.get("cx"))
                cy = active_target.get("y", active_target.get("cy"))

                if "lastDetection" in active_target:
                    selected_detection = active_target["lastDetection"]
                elif "cx" in active_target:
                    selected_detection = active_target
                else:
                    selected_detection = None

                pan, tilt = pixel_to_body_angles(cx, cy, gimbal_pan, gimbal_tilt, camera)
                self._candidate_pan_deg = pan
                self._candidate_tilt_deg = tilt

                setpoint = {"pan_deg": pan, "tilt_deg": tilt}
                self._candidate_confirm_count += 1
                self._last_seen_time = sim_time

                if confirmed_candidate and confirmed_candidate.get("confirmed"):
                    if kalman:
                        kalman.init(pan, tilt, sim_time)
                    self._transition_to("TRACK", sim_time, "Confirmed beacon via blink code ID")
                    emitted_events.append(self._event_log[-1])
                elif (
                    not all_candidates
                    and self._candidate_confirm_count >= self._cfg.acquire_confirm_frames
                ):
                    if kalman:
                        kalman.init(pan, tilt, sim_time)
                    self._transition_to(
                        "TRACK",
                        sim_time,
                        f"Confirmed candidate over {self._candidate_confirm_count} frames",
                    )
                    emitted_events.append(self._event_log[-1])
            else:
                setpoint = {
                    "pan_deg": self._candidate_pan_deg,
                    "tilt_deg": self._candidate_tilt_deg,
                }
                if sim_time - self._last_seen_time > self._cfg.acquire_timeout_sec:
                    self._transition_to("SEARCH", sim_time, "Acquire timeout without confirmation")
                    emitted_events.append(self._event_log[-1])

        elif self.state == "TRACK":
            mode = "TRACK"
            best_gated = None
            min_gate_dist = float("inf")

            if (
                confirmed_candidate
                and confirmed_candidate.get("lastDetection")
                and confirmed_candidate.get("missedFrames", 0) == 0
            ):
                target_detections = [confirmed_candidate["lastDetection"]]
            elif all_candidates:
                target_detections = []
            else:
                target_detections = detections

            if kalman:
                kalman.predict(sim_time)

                for d in target_detections:
                    pan, tilt = pixel_to_body_angles(
                        d["cx"], d["cy"], gimbal_pan, gimbal_tilt, camera
                    )
                    gate_dist = kalman.get_innovation_gate(pan, tilt)
                    if gate_dist <= gate_sigma and gate_dist < min_gate_dist:
                        min_gate_dist = gate_dist
                        best_gated = {"detection": d, "pan_deg": pan, "tilt_deg": tilt}

            if best_gated:
                selected_detection = best_gated["detection"]
                self._consecutive_misses = 0
                self._last_seen_time = sim_time
                if kalman:
                    kalman.update(best_gated["pan_deg"], best_gated["tilt_deg"], sim_time)
            else:
                self._consecutive_misses += 1
                if self._consecutive_misses > self._cfg.lost_miss_frames:
                    self._transition_to(
                        "LOST",
                        sim_time,
                        f"Consecutive misses exceeded {self._cfg.lost_miss_frames}",
                    )
                    emitted_events.append(self._event_log[-1])

            if kalman:
                k_state = kalman.get_state()
                setpoint = {"pan_deg": k_state["pan_deg"], "tilt_deg": k_state["tilt_deg"]}

        elif self.state == "LOST":
            mode = "TRACK"
            if kalman:
                kalman.predict(sim_time)

            recovered = None
            if kalman:
                for d in detections:
                    if d["snr"] < min_snr:
                        continue
                    pan, tilt = pixel_to_body_angles(
                        d["cx"], d["cy"], gimbal_pan, gimbal_tilt, camera
                    )
                    gate_dist = kalman.get_innovation_gate(pan, tilt)
                    if gate_dist <= gate_sigma:
                        recovered = {"detection": d, "pan_deg": pan, "tilt_deg": tilt}
                        break

            if recovered:
                selected_detection = recovered["detection"]
                if kalman:
                    kalman.update(recovered["pan_deg"], recovered["tilt_deg"], sim_time)
                self._transition_to(
                    "TRACK", sim_time, "Reacquired detection within Kalman gate during coasting"
                )
                emitted_events.append(self._event_log[-1])
            elif sim_time - self._state_start_time > self._cfg.coast_max_sec:
                if kalman:
                    ks = kalman.get_state()
                    self._spiral_center = {"pan_deg": ks["pan_deg"], "tilt_deg": ks["tilt_deg"]}
                else:
                    self._spiral_center = {"pan_deg": gimbal_pan, "tilt_deg": gimbal_tilt}
                self._transition_to(
                    "REACQUIRE",
                    sim_time,
                    f"Coast duration exceeded {self._cfg.coast_max_sec}s",
                )
                emitted_events.append(self._event_log[-1])

            if kalman:
                k_state = kalman.get_state()
                setpoint = {"pan_deg": k_state["pan_deg"], "tilt_deg": k_state["tilt_deg"]}

        elif self.state == "REACQUIRE":
            mode = "GOTO"
            scan = spiral(sim_time - self._state_start_time, self._spiral_center, self._cfg, camera)
            setpoint = {"pan_deg": scan["pan_deg"], "tilt_deg": scan["tilt_deg"]}

            if best_detection and best_detection["snr"] >= min_snr:
                selected_detection = best_detection
                pan, tilt = pixel_to_body_angles(
                    best_detection["cx"],
                    best_detection["cy"],
                    gimbal_pan,
                    gimbal_tilt,
                    camera,
                )
                self._candidate_pan_deg = pan
                self._candidate_tilt_deg = tilt
                self._transition_to("ACQUIRE", sim_time, "Detection found in REACQUIRE spiral")
                emitted_events.append(self._event_log[-1])
            elif scan.get("done"):
                self._transition_to(
                    "SEARCH", sim_time, "Reacquire spiral completed without detection"
                )
                emitted_events.append(self._event_log[-1])

        return {
            "state": self.state,
            "mode": mode,
            "setpoint": setpoint,
            "selected_detection": selected_detection,
            "events": emitted_events,
        }

    def reset(self, sim_time: float = 0.0) -> None:
        """Reset state machine to initial SEARCH state."""
        self.state = "SEARCH"
        self._state_start_time = sim_time
        self._last_seen_time = sim_time
        self._candidate_confirm_count = 0
        self._consecutive_misses = 0
        self._event_log.clear()

    def get_events(self) -> list[dict[str, Any]]:
        """Return the transition event log."""
        return self._event_log
