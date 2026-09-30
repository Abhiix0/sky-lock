# Sky Lock - Configuration Reference (`docs/CONFIG.md`)

This document provides a comprehensive reference table for all configuration parameters defined across `src/tracking/config.js`.

---

## 1. Optical Beacon Configuration (`BEACON_CONFIG`)

| Key | Type | Unit | Default | PS Reference | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `enabled` | `boolean` | -- | `true` | Sec 3.1 | Enables or disables the optical beacon emitter on Target Satellite (S-2). |
| `color` | `number` (hex) | RGB | `0xff2bd6` | Sec 3.1 | Hexadecimal color of the beacon halo (saturated magenta). |
| `coreRadiusPx` | `number` | pixels | `3` | Sec 3.1 | Core bright spot radius on the virtual camera focal plane. |
| `haloRadiusPx` | `number` | pixels | `12` | Sec 3.1 | Point-spread-function (PSF) halo glow radius. |
| `brightness` | `number` | [0.0, 1.0] | `1.0` | Sec 3.1 | Base optical emitter radiant intensity multiplier. |
| `blinkHz` | `number` | Hz | `0` | Sec 3.2 | Base square-wave blink frequency (0 = steady CW emission). |
| `blinkDuty` | `number` | [0.0, 1.0] | `0.5` | Sec 3.2 | Blink duty cycle for periodic pulsing. |
| `hideTargetBodyInFeed`| `boolean`| -- | `true` | Sec 2.2 | Hides S-2 satellite bus geometry in camera feed (point-source mode). |
| `showMarkerInMainView`| `boolean`| -- | `false` | Sec 2.2 | Displays visual beacon helper ring in the primary 3D orbital viewport. |

---

## 2. Beacon Coding & Identification (`BEACON_CODE`, `ID_CONFIG`)

| Key | Type | Unit | Default | PS Reference | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `BEACON_CODE.bits` | `string` | binary | `'10110010'` | Sec 3.2 | 8-bit periodic identification pattern for matched-filter correlation. |
| `BEACON_CODE.bitPeriodSec` | `number` | seconds | `0.1` | Sec 3.2 | Duration per bit (100 ms corresponds to 3 frames at 30 Hz). |
| `BEACON_CODE.samplesPerBit`| `number` | samples | `3` | Sec 3.2 | Sensor sampling rate multiplier per code bit. |
| `BEACON_CODE.mode` | `string` | enum | `'steady'` | Sec 3.2 | Beacon operational mode: `'steady'` (baseline) or `'code'` (blink modulation). |
| `ID_CONFIG.idThreshold` | `number` | [0.0, 1.0] | `0.70` | Sec 3.2 | Pearson correlation coefficient threshold to confirm beacon identity. |
| `ID_CONFIG.idConfirmFrames` | `number` | frames | `3` | Sec 3.2 | Consecutive frames above threshold required to declare lock confirmed. |
| `ID_CONFIG.historyWindowFrames`| `number` | frames | `48` | Sec 3.2 | Sliding window buffer depth (N = 2 × 8 bits × 3 samples = 48 frames). |
| `ID_CONFIG.gateInitialPx` | `number` | pixels | `35` | Sec 3.3 | Initial spatial validation gate radius for candidate track association. |
| `ID_CONFIG.gateGrowthPxPerFrame`| `number` | px/frame | `3` | Sec 3.3 | Spatial gate expansion rate per frame during coasting/missed frames. |
| `ID_CONFIG.gateMaxPx` | `number` | pixels | `90` | Sec 3.3 | Upper boundary limit for candidate tracking association gate. |
| `ID_CONFIG.maxMissFrames` | `number` | frames | `6` | Sec 3.3 | Consecutive undetected frames before candidate track is pruned. |
| `ID_CONFIG.intensityThreshold` | `number` | LSB [0-255] | `40` | Sec 3.3 | Minimum peak pixel brightness required to establish a candidate track. |

---

## 3. Decoy Clutter Sources (`DECOY_CONFIG`)

| Key | Type | Unit | Default | PS Reference | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `enabled` | `boolean` | -- | `false` | Sec 3.4 | Enables deceptive decoy optical emitters in the vicinity of S-2. |
| `count` | `number` | integer | `3` | Sec 3.4 | Number of competing decoy point sources spawned. |
| `color` | `number` (hex) | RGB | `0xff2bd6` | Sec 3.4 | Decoy optical emission spectrum (matches true beacon chroma). |
| `brightness` | `number` | [0.0, 1.0] | `1.0` | Sec 3.4 | Decoy emitter peak radiant intensity. |
| `steadyRatio` | `number` | [0.0, 1.0] | `0.5` | Sec 3.4 | Probability that a spawned decoy emits continuous steady light. |
| `rateMinHz` | `number` | Hz | `3.0` | Sec 3.4 | Minimum blink modulation frequency for non-steady decoys. |
| `rateMaxHz` | `number` | Hz | `8.0` | Sec 3.4 | Maximum blink modulation frequency for non-steady decoys. |
| `angularOffsetMinDeg`| `number` | degrees | `2.0` | Sec 3.4 | Minimum angular separation from true target satellite. |
| `angularOffsetMaxDeg`| `number` | degrees | `8.0` | Sec 3.4 | Maximum angular separation from true target satellite. |
| `angularDriftDegPerSec`| `number`| deg/s | `0.2` | Sec 3.4 | Angular trajectory drift rate of decoys relative to target. |

---

## 4. Virtual Camera & Gimbal Hardware (`CAMERA_CONFIG`, `SLEW_PRESETS`)

| Key | Type | Unit | Default | PS Reference | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `fovDeg` | `number` | degrees | `20.0` | Sec 2.1 | Camera horizontal field of view. |
| `width` | `number` | pixels | `640` | Sec 2.1 | Focal plane array horizontal pixel resolution. |
| `height` | `number` | pixels | `480` | Sec 2.1 | Focal plane array vertical pixel resolution. |
| `fps` | `number` | Hz | `30` | Sec 2.1 | Camera sensor frame capture rate. |
| `near` | `number` | distance | `0.1` | Sec 2.1 | Frustum near clipping plane. |
| `far` | `number` | distance | `2000.0` | Sec 2.1 | Frustum far clipping plane. |
| `activeSlewPreset` | `string` | enum | `'baseline'` | Sec 2.3 | Active gimbal servo speed preset (`'stress'`, `'baseline'`, `'fast'`). |
| `maxSlewRateDegPerSec` | `number` | deg/s | `45.0` | Sec 2.3 | Maximum servo angular velocity limit (`baseline` preset). |
| `maxAccelDegPerSec2` | `number` | deg/s² | `120.0` | Sec 2.3 | Maximum servo angular acceleration limit. |
| `panRangeDeg` | `number[]` | degrees | `[-180, 180]`| Sec 2.3 | Gimbal azimuth continuous mechanical travel range. |
| `tiltRangeDeg` | `number[]` | degrees | `[-60, 60]` | Sec 2.3 | Gimbal elevation mechanical travel stops. |
| `SLEW_PRESETS.stress` | `number` | deg/s | `30.0` | Sec 2.3 | Problem statement stress-test slew rate limit. |
| `SLEW_PRESETS.baseline`| `number` | deg/s | `45.0` | Sec 2.3 | Nominal operational tracking slew rate limit. |
| `SLEW_PRESETS.fast` | `number` | deg/s | `60.0` | Sec 2.3 | High-speed reacquisition slew rate limit. |

---

## 5. Blob Detector (`DETECTOR_CONFIG`)

| Key | Type | Unit | Default | PS Reference | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mode` | `string` | enum | `'chroma'` | Sec 2.4 | Detection metric: `'chroma'` (magenta color filter) or `'luma'` (brightness). |
| `threshold` | `number` | LSB [0-255] | `128` | Sec 2.4 | Binary segmentation discrimination threshold. |
| `minBlobArea` | `number` | pixels | `2` | Sec 2.4 | Connected component minimum pixel area filter. |
| `maxBlobArea` | `number` | pixels | `400` | Sec 2.4 | Connected component maximum pixel area filter (rejects Earth albedo). |
| `minCircularity` | `number` | [0.0, 1.0] | `0.35` | Sec 2.4 | Compactness filter $4\pi A / P^2$ to reject non-circular background clutter. |
| `maxAspect` | `number` | ratio | `3.0` | Sec 2.4 | Bounding box aspect ratio $(w/h \text{ or } h/w)$ upper threshold. |

---

## 6. Kalman Filter State Estimator (`KALMAN_CONFIG`)

| Key | Type | Unit | Default | PS Reference | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `sigmaProcess` | `number` | deg/s² | `0.8` | Sec 2.5 | Acceleration process noise spectral density $q_{\text{pos}}$ for line-of-sight. |
| `sigmaProcessRate` | `number` | deg/s² | `2.5` | Sec 2.5 | Rate process noise spectral density $q_{\text{vel}}$. |
| `sigmaMeasure` | `number` | degrees | `0.05` | Sec 2.5 | Sensor angular measurement error standard deviation $R$. |
| `maxCoastTimeSec` | `number` | seconds | `12.0` | Sec 2.5 | Maximum orbital coasting duration during total signal occlusion. |
| `maxCovariance` | `number` | deg² | `100.0` | Sec 2.5 | Covariance trace threshold triggering automatic state re-initialization. |

---

## 7. Gimbal PID Rate Controller (`CONTROLLER_CONFIG`)

| Key | Type | Unit | Default | PS Reference | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `kp` | `number` | s⁻¹ | `3.2` | Sec 2.6 | Proportional gain for angular pointing error reduction. |
| `ki` | `number` | s⁻² | `0.45` | Sec 2.6 | Integral gain for steady-state orbital drift cancellation. |
| `kd` | `number` | dimensionless | `0.18` | Sec 2.6 | Derivative gain for rate damping. |
| `ff` | `number` | dimensionless | `1.0` | Sec 2.6 | Feed-forward velocity scale from Kalman state velocity vector. |
| `derivativeFilterHz` | `number` | Hz | `15.0` | Sec 2.6 | Low-pass filter cutoff frequency for derivative error term. |
| `integratorLimit` | `number` | deg/s | `15.0` | Sec 2.6 | Anti-windup clamping saturation limit for integral state. |

---

## 8. Acquisition & Search State Machine (`TRACKING_CONFIG`)

| Key | Type | Unit | Default | PS Reference | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `gateRadiusPx` | `number` | pixels | `35` | Sec 2.7 | Acceptance gate radius for transitioning `SEARCH` $\to$ `ACQUIRE`. |
| `confirmFrames` | `number` | frames | `3` | Sec 2.7 | Multi-frame persistence count required to transition `ACQUIRE` $\to$ `TRACK`. |
| `missThreshold` | `number` | frames | `5` | Sec 2.7 | Consecutive missed frames in `TRACK` before declaring `LOST`. |
| `coastingTimeoutSec` | `number` | seconds | `12.0` | Sec 2.7 | Coastal propagation timeout in `LOST` before transitioning to `REACQUIRE`. |
| `reacquireTimeoutSec` | `number` | seconds | `15.0` | Sec 2.7 | Expanding spiral timeout in `REACQUIRE` before resetting to `SEARCH`. |
| `reacquireSpiralRateDegS`| `number` | deg/s | `30.0` | Sec 2.7 | Tangential scanning velocity along Archimedean spiral path. |
| `reacquireSpiralPitchDeg`| `number` | degrees | `16.0` | Sec 2.7 | Radial track pitch separation per 360° spiral turn ($FOV \times [1 - \text{overlap}]$). |
| `tiltScanLimitDeg` | `number` | degrees | `55.0` | Sec 2.7 | Full raster coverage elevation envelope stop boundaries ($\pm 55^\circ$). |
| `scanRateDegS` | `number` | deg/s | `35.0` | Sec 2.7 | Raster scan horizontal sweep angular rate. |
| `overlap` | `number` | fraction | `0.20` | Sec 2.7 | Overlap ratio between adjacent raster rows ($20\%$). |

---

## 9. Space Disturbance Presets (`DISTURBANCE_PRESETS`)

| Key | Type | Unit | Default (MED) | Description |
| :--- | :--- | :--- | :--- | :--- |
| `wanderRmsPx` | `number` | pixels RMS | `2.5` | Atmospheric beam wander standard deviation. |
| `wanderCornerHz` | `number` | Hz | `2.0` | Beam wander low-pass filter corner frequency. |
| `scintillationSigma` | `number` | dimensionless | `0.35` | Log-normal intensity irradiance variance. |
| `jitterRmsDeg` | `number` | degrees RMS | `0.15` | Satellite bus reaction-wheel high-frequency mechanical vibration. |
| `vibrationHz` | `number` | Hz | `10.0` | Center frequency of structural mechanical resonance. |
| `noiseSigma` | `number` | LSB | `10.0` | Gaussian zero-mean sensor focal plane read noise. |
| `hotPixelsCount` | `number` | count | `6` | Persistent defective saturated pixels on sensor. |
| `blurRadiusPx` | `number` | pixels | `2` | Optical defocus / wavefront blur kernel radius. |
| `dropProbability` | `number` | fraction | `0.05` | Sensor transmission frame drop probability ($5\%$). |

---

## 10. Global Runtime Flags

| Key | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `DEBUG` | `boolean` | `false` | Master runtime logging flag. When `false`, suppresses high-frequency per-frame tracking diagnostics. |
