"""PointingController calculating commanded gimbal motor angular rates."""

from __future__ import annotations

from skylock.config.models import CameraConfig, ControlConfig
from skylock.control.pid import PID
from skylock.core.enums import ControlIntentMode, ControlMode
from skylock.core.geometry import angular_diff_deg
from skylock.core.types import ControlCommand, ControlIntent, Pointing, TargetEstimate


class PointingController:
    """Line-of-sight tracking controller converting ControlIntent to motor rate commands.

    Strict contract:
    - Never accepts, references, or imports GroundTruthSample.
    - Operates purely on ControlIntent, TargetEstimate, and Pointing telemetry.
    """

    def __init__(
        self,
        control_cfg: ControlConfig | None = None,
        camera_cfg: CameraConfig | None = None,
        max_slew_rate_deg_s: float = 10.0,
    ) -> None:
        """Initialize PointingController.

        Args:
            control_cfg: PID gains and controller settings.
            camera_cfg: Camera parameters for IFOV and slew calculation.
            max_slew_rate_deg_s: Upper velocity cap in deg/s (hard ceiling <= 10.0).
        """
        self.control_cfg = control_cfg if control_cfg is not None else ControlConfig()
        self.camera_cfg = camera_cfg if camera_cfg is not None else CameraConfig()
        self.max_slew_rate_deg_s = min(10.0, float(max_slew_rate_deg_s))

        self.pid_pan = PID(
            kp=self.control_cfg.kp,
            ki=self.control_cfg.ki,
            kd=self.control_cfg.kd,
            d_alpha=self.control_cfg.d_filter_alpha,
            i_clamp=self.control_cfg.integral_clamp,
        )
        self.pid_tilt = PID(
            kp=self.control_cfg.kp,
            ki=self.control_cfg.ki,
            kd=self.control_cfg.kd,
            d_alpha=self.control_cfg.d_filter_alpha,
            i_clamp=self.control_cfg.integral_clamp,
        )

        self._mode: ControlMode = (
            ControlMode.MANUAL if self.control_cfg.mode == "MANUAL" else ControlMode.AUTO
        )
        self._manual_pan_rate: float = 0.0
        self._manual_tilt_rate: float = 0.0

    @property
    def mode(self) -> ControlMode:
        """Current operating mode (AUTO or MANUAL)."""
        return self._mode

    def set_mode(self, mode: ControlMode | str) -> None:
        """Set operating mode (AUTO or MANUAL)."""
        if isinstance(mode, str):
            self._mode = ControlMode.MANUAL if mode.upper() == "MANUAL" else ControlMode.AUTO
        else:
            self._mode = mode

    def set_manual_rate(self, pan_rate_deg_s: float, tilt_rate_deg_s: float) -> None:
        """Set manual angular rates to be executed when mode is MANUAL."""
        self._manual_pan_rate = float(pan_rate_deg_s)
        self._manual_tilt_rate = float(tilt_rate_deg_s)

    def reset(self) -> None:
        """Reset internal PID controllers and manual rates."""
        self.pid_pan.reset()
        self.pid_tilt.reset()
        self._manual_pan_rate = 0.0
        self._manual_tilt_rate = 0.0
        self._mode = (
            ControlMode.MANUAL if self.control_cfg.mode == "MANUAL" else ControlMode.AUTO
        )

    def step(
        self,
        intent: ControlIntent,
        estimate: TargetEstimate | None,
        pointing: Pointing | None,
        dt: float,
    ) -> ControlCommand:
        """Calculate commanded gimbal angular rates for the current frame step.

        Args:
            intent: Desired control intent from tracking state machine.
            estimate: Filtered target estimate or None.
            pointing: Current gimbal pointing telemetry or None.
            dt: Frame timestep duration in seconds.

        Returns:
            ControlCommand containing pan and tilt rates in deg/s.
        """
        max_slew = self.max_slew_rate_deg_s

        if self._mode == ControlMode.MANUAL:
            pan_cmd = max(-max_slew, min(max_slew, self._manual_pan_rate))
            tilt_cmd = max(-max_slew, min(max_slew, self._manual_tilt_rate))
            return ControlCommand(pan_rate_deg_s=pan_cmd, tilt_rate_deg_s=tilt_cmd)

        if intent.mode == ControlIntentMode.HOLD or dt <= 0.0:
            self.pid_pan.reset()
            self.pid_tilt.reset()
            return ControlCommand(pan_rate_deg_s=0.0, tilt_rate_deg_s=0.0)

        if intent.mode == ControlIntentMode.GOTO:
            pt = pointing if pointing is not None else Pointing(0.0, 0.0)
            err_pan = angular_diff_deg(intent.setpoint_pan_deg, pt.pan_deg)
            err_tilt = intent.setpoint_tilt_deg - pt.tilt_deg

            # Proportional slew rate toward setpoint
            k_goto = self.control_cfg.kp
            pan_cmd = max(-max_slew, min(max_slew, k_goto * err_pan))
            tilt_cmd = max(-max_slew, min(max_slew, k_goto * err_tilt))
            return ControlCommand(pan_rate_deg_s=pan_cmd, tilt_rate_deg_s=tilt_cmd)

        # intent.mode == ControlIntentMode.TRACK
        err_x_px, err_y_px = (
            intent.image_error_px if intent.image_error_px is not None else (0.0, 0.0)
        )

        # Deadband thresholding
        deadband = self.control_cfg.deadband_px
        if abs(err_x_px) < deadband:
            err_x_px = 0.0
        if abs(err_y_px) < deadband:
            err_y_px = 0.0

        # Convert image error to angular angle errors
        ifov_h = self.camera_cfg.fov_h_deg / self.camera_cfg.width
        ifov_v = self.camera_cfg.fov_v_deg / self.camera_cfg.height
        err_pan_deg = err_x_px * ifov_h
        err_tilt_deg = -err_y_px * ifov_v

        # Feed-forward angular velocity from target kinematic estimate
        ff_pan = self.control_cfg.kff * estimate.pan_rate if estimate is not None else 0.0
        ff_tilt = self.control_cfg.kff * estimate.tilt_rate if estimate is not None else 0.0

        # PID integration
        u_pan = self.pid_pan.step(err_pan_deg, dt, limit=max_slew) + ff_pan
        u_tilt = self.pid_tilt.step(err_tilt_deg, dt, limit=max_slew) + ff_tilt

        pan_cmd = max(-max_slew, min(max_slew, u_pan))
        tilt_cmd = max(-max_slew, min(max_slew, u_tilt))

        return ControlCommand(pan_rate_deg_s=pan_cmd, tilt_rate_deg_s=tilt_cmd)


__all__ = ("PointingController",)
