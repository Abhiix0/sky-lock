# Sky Lock Benchmark Statistical Tables

- **Generated At**: `2026-09-29T14:40:25.129Z`
- **Total Wall-Clock Time**: `79.1 s`
- **Environment**: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.7977.130 Electron/44.4.5 Safari/537.36`
- **Total Scenario Runs**: `24` (8 scenarios × 3 seeds: Seeds [1, 2, 3])

## 1. Run Configuration Parameters

| Parameter Category | Key / Subsystem | Configured Value | Unit | Description |
| :--- | :--- | :--- | :--- | :--- |
| Camera | `resolution` | 640 × 480 | px | Gimbal sensor optical matrix |
| Camera | `fovDeg` | 20 | deg | Narrow FOV tracking optic |
| Camera | `pixelScale` | 0.436 | µrad/px | Spatial angular resolution |
| Actuator | `slewRateMax` | 15 | deg/s | Maximum 2-axis gimbal rate |
| Actuator | `slewAccelMax` | 30 | deg/s² | Maximum gimbal acceleration |
| Kalman Filter | `qPos / qVel` | 0.05 / 0.5 | - | Process noise covariance diagonal |
| Kalman Filter | `rPos` | 2 | px² | Measurement noise variance |
| Controller | `kp / ki / kd` | 4 / 0.5 / 0.2 | - | Discrete PID servo loop gains |
| Controller | `feedForward` | Enabled | - | State-prediction velocity feed-forward |
| Beacon ID | `bitPeriodSec` | 0.1 | s | Optical Manchester pulse interval |
| Beacon ID | `codeSequence` | `0b10110010` | - | 8-bit unforgeable optical signature |

## 2. Acquisition Time, Lock Retention & Reacquisition Performance

| Scenario | Description | Disturbances | Decoys | Slew Mode | Acquisition Time (s) | Lock Retention (%) | Reacquisition Mean (s) | False Locks |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **S0** | Clean Baseline | `OFF` | No | `baseline` | 0.00 ± 0.00 | **0.0 ± 0.0%** | 0.00 ± 0.00 | **0** |
| **S1** | Low Disturbances | `LOW` | No | `baseline` | 0.00 ± 0.00 | **0.0 ± 0.0%** | 0.00 ± 0.00 | **0** |
| **S2** | Medium Disturbances | `MED` | No | `baseline` | 0.00 ± 0.00 | **0.0 ± 0.0%** | 0.00 ± 0.00 | **0** |
| **S3** | High Disturbances | `HIGH` | No | `baseline` | 0.00 ± 0.00 | **0.0 ± 0.0%** | 0.00 ± 0.00 | **0** |
| **S4** | Medium + 3 Decoys | `MED` | Yes (3) | `baseline` | 0.00 ± 0.00 | **0.0 ± 0.0%** | 0.00 ± 0.00 | **0** |
| **S5** | Occlusion at 4x Speed | `OFF` | No | `baseline` | 0.00 ± 0.00 | **0.0 ± 0.0%** | 0.00 ± 0.00 | **0** |
| **S6** | PS-Slew (30°/s) Stress | `OFF` | No | `ps` | 0.00 ± 0.00 | **0.0 ± 0.0%** | 0.00 ± 0.00 | **0** |
| **S7** | High + Decoys Stress | `HIGH` | Yes (3) | `baseline` | 0.00 ± 0.00 | **0.0 ± 0.0%** | 0.00 ± 0.00 | **0** |

## 3. Pointing Error, System Latency & Frame Rate

| Scenario | Pointing Err Mean (px) | Pointing Err RMS (px) | Pointing Err RMS (mrad) | Pointing Err Max (px) | Processing Latency (ms) | Render FPS |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **S0** | 0.00 ± 0.00 | **0.00 ± 0.00** | **0.000 ± 0.000** | 0.0 ± 0.0 | 0.65 ± 1.13 | 54.7 ± 9.2 |
| **S1** | 0.00 ± 0.00 | **0.00 ± 0.00** | **0.000 ± 0.000** | 0.0 ± 0.0 | 0.00 ± 0.00 | 60.0 ± 0.0 |
| **S2** | 0.00 ± 0.00 | **0.00 ± 0.00** | **0.000 ± 0.000** | 0.0 ± 0.0 | 0.00 ± 0.00 | 60.0 ± 0.0 |
| **S3** | 0.00 ± 0.00 | **0.00 ± 0.00** | **0.000 ± 0.000** | 0.0 ± 0.0 | 0.00 ± 0.00 | 60.0 ± 0.0 |
| **S4** | 0.00 ± 0.00 | **0.00 ± 0.00** | **0.000 ± 0.000** | 0.0 ± 0.0 | 0.00 ± 0.00 | 60.0 ± 0.0 |
| **S5** | 0.00 ± 0.00 | **0.00 ± 0.00** | **0.000 ± 0.000** | 0.0 ± 0.0 | 0.87 ± 1.50 | 60.0 ± 0.0 |
| **S6** | 0.00 ± 0.00 | **0.00 ± 0.00** | **0.000 ± 0.000** | 0.0 ± 0.0 | 0.00 ± 0.00 | 60.0 ± 0.0 |
| **S7** | 0.00 ± 0.00 | **0.00 ± 0.00** | **0.000 ± 0.000** | 0.0 ± 0.0 | 0.00 ± 0.00 | 60.0 ± 0.0 |

## 4. Granular Scenario Run Log (All Seeds)

| Scenario | Seed | Observable (s) | Tracked (s) | Retention (%) | Acq Time (s) | Pointing RMS (px) | Latency Mean (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| S0 | 1 | 189.6 | 0.0 | 0.0% | N/A | 0.00 | 1.95 |
| S0 | 2 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S0 | 3 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S1 | 1 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S1 | 2 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S1 | 3 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S2 | 1 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S2 | 2 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S2 | 3 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S3 | 1 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S3 | 2 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S3 | 3 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S4 | 1 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S4 | 2 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S4 | 3 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S5 | 1 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 2.60 |
| S5 | 2 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S5 | 3 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S6 | 1 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S6 | 2 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S6 | 3 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S7 | 1 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S7 | 2 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
| S7 | 3 | 0.0 | 0.0 | 0.0% | N/A | 0.00 | 0.00 |
