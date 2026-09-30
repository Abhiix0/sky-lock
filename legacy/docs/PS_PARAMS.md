# Problem Statement (PS) Parameter Mapping

| PS Parameter | Value | Config Key | Status |
| --- | --- | --- | --- |
| Optical Field of View (FOV) | 20° (vertical) | `fovDeg` | Implemented |
| Sensor Resolution | 640 × 480 px | `width`, `height` | Implemented |
| Camera Feed Rate | 30 Hz | `feedRateHz` | Implemented |
| Pan Range | ±180° | `panLimitDeg` | Implemented |
| Tilt Range | ±90° | `tiltLimitDeg` | Implemented |
| Max Gimbal Slew Rate | 30°/s (stress), 45°/s (baseline) | `maxSlewRateDegPerSec`, `SLEW_PRESETS` | Implemented |
| Max Slew Acceleration | 120°/s² | `maxSlewAccelDegPerSec2` | Implemented |
| Simulation Timestep Rate | 120 Hz | `simStepHz` | Implemented |
| Max Feed Frames Per Render | 2 | `maxFeedFramesPerRender` | Implemented |
| Pan Wrap-around | Enabled (true) | `panWrap` | Implemented |
