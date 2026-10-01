# SkyLock Validation Report

> **Generated:** 2026-09-30T10:13:12.802352+00:00  
> **SkyLock version:** 0.1.0  
> **Source:** D:\Abhiix0\Learning Projects\skylock\sky-lock\runs\validation  
> **Note:** All numbers are read directly from JSON run files — not hand-typed.

---

## Headline Verdict

| Runs | PASS | FAIL | INDETERMINATE | NOT_RUN |
|------|------|------|---------------|---------|
| 30 | 0 | 4 | 26 | 0 |

**❌ OVERALL: FAIL**

---

## Per-Requirement Verdict Table

Each cell shows the verdict for that scenario+seed run.

| Scenario | Seed | Acq ≤ 2 s | Track ≤ 10 px | Loss < 5% | Reacq ≤ 1 s | FPS ≥ 20 | Overall |
|------------|------------|------------|------------|------------|------------|------------|------------|
| S01_line_clean | 1 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S01_line_clean | 2 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S02_circle_clean | 1 | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S02_circle_clean | 2 | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S03_fig8_clean | 1 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S03_fig8_clean | 2 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S04_random_clean | 1 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S04_random_clean | 2 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S05_line_spec_noise | 1 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S05_line_spec_noise | 2 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S06_jitter20 | 1 | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S06_jitter20 | 2 | ✅ PASS | ❌ FAIL | ❌ FAIL | ✅ PASS | ✅ PASS | ❌ FAIL |
| S07_platform20 | 1 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S07_platform20 | 2 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S08_haze | 1 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S08_haze | 2 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S09_fog | 1 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S09_fog | 2 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S10_rain | 1 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S10_rain | 2 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S11_low_light | 1 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S11_low_light | 2 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S12_occlusion_reacq | 1 | ✅ PASS | ✅ PASS | ❌ FAIL | ✅ PASS | ✅ PASS | ❌ FAIL |
| S12_occlusion_reacq | 2 | ✅ PASS | ✅ PASS | ❌ FAIL | ✅ PASS | ✅ PASS | ❌ FAIL |
| S13_all_disturbances | 1 | ✅ PASS | ❌ FAIL | ❌ FAIL | ✅ PASS | ✅ PASS | ❌ FAIL |
| S13_all_disturbances | 2 | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S14_multi_target | 1 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S14_multi_target | 2 | ✅ PASS | ✅ PASS | ✅ PASS | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S15_slew10 | 1 | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ✅ PASS | ⚠️ INDET |
| S15_slew10 | 2 | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ⚠️ INDET | ✅ PASS | ⚠️ INDET |

## Per-Metric Detail

Key measured values per run. `(status)` shown for non-MEASURED metrics.

| Scenario | Seed | Acq time (start) | Acq time (obs) | Tracking error | Pointing error | Reacq time | Loss rate | Pipeline FPS |
|------------------|------------------|------------------|------------------|------------------|------------------|------------------|------------------|------------------|
| S01_line_clean | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S01_line_clean | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S02_circle_clean | 1 | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (MEASURED) |
| S02_circle_clean | 2 | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (MEASURED) |
| S03_fig8_clean | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S03_fig8_clean | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S04_random_clean | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S04_random_clean | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S05_line_spec_noise | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S05_line_spec_noise | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S06_jitter20 | 1 | (NOT_ACQUIRED) | (NOT_ACQUIRED) | (NOT_ACQUIRED) | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (MEASURED) |
| S06_jitter20 | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) |
| S07_platform20 | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S07_platform20 | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S08_haze | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S08_haze | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S09_fog | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S09_fog | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S10_rain | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S10_rain | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S11_low_light | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S11_low_light | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S12_occlusion_reacq | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) |
| S12_occlusion_reacq | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) |
| S13_all_disturbances | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) |
| S13_all_disturbances | 2 | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (MEASURED) |
| S14_multi_target | 1 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S14_multi_target | 2 | (MEASURED) | (MEASURED) | (MEASURED) | (MEASURED) | (NOT_RUN) | (MEASURED) | (MEASURED) |
| S15_slew10 | 1 | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (MEASURED) |
| S15_slew10 | 2 | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (NOT_ACQUIRED) | (NOT_RUN) | (NOT_ACQUIRED) | (MEASURED) |

## Failures and Root-Cause Notes

Scenarios that produced a FAIL verdict:

### S06_jitter20 (seed=2)

Failed requirements: `tracking_error`, `target_loss_rate`

- **Track ≤ 10 px**: measured `(MEASURED)`
- **Loss < 5%**: measured `(MEASURED)`

> Root-cause: see scenario description and disturbance config.

### S12_occlusion_reacq (seed=1)

Failed requirements: `target_loss_rate`

- **Loss < 5%**: measured `(MEASURED)`

> Root-cause: see scenario description and disturbance config.

### S12_occlusion_reacq (seed=2)

Failed requirements: `target_loss_rate`

- **Loss < 5%**: measured `(MEASURED)`

> Root-cause: see scenario description and disturbance config.

### S13_all_disturbances (seed=1)

Failed requirements: `tracking_error`, `target_loss_rate`

- **Track ≤ 10 px**: measured `(MEASURED)`
- **Loss < 5%**: measured `(MEASURED)`

> Root-cause: see scenario description and disturbance config.

## Indeterminate Results

These runs could not be fully evaluated (e.g. target never acquired, reacquisition never triggered):

- **S01_line_clean** (seed=1): `reacquisition_time`
- **S01_line_clean** (seed=2): `reacquisition_time`
- **S02_circle_clean** (seed=1): `acquisition_time`, `tracking_error`, `target_loss_rate`, `reacquisition_time`
- **S02_circle_clean** (seed=2): `acquisition_time`, `tracking_error`, `target_loss_rate`, `reacquisition_time`
- **S03_fig8_clean** (seed=1): `reacquisition_time`
- **S03_fig8_clean** (seed=2): `reacquisition_time`
- **S04_random_clean** (seed=1): `reacquisition_time`
- **S04_random_clean** (seed=2): `reacquisition_time`
- **S05_line_spec_noise** (seed=1): `reacquisition_time`
- **S05_line_spec_noise** (seed=2): `reacquisition_time`
- **S06_jitter20** (seed=1): `acquisition_time`, `tracking_error`, `target_loss_rate`, `reacquisition_time`
- **S07_platform20** (seed=1): `reacquisition_time`
- **S07_platform20** (seed=2): `reacquisition_time`
- **S08_haze** (seed=1): `reacquisition_time`
- **S08_haze** (seed=2): `reacquisition_time`
- **S09_fog** (seed=1): `reacquisition_time`
- **S09_fog** (seed=2): `reacquisition_time`
- **S10_rain** (seed=1): `reacquisition_time`
- **S10_rain** (seed=2): `reacquisition_time`
- **S11_low_light** (seed=1): `reacquisition_time`
- **S11_low_light** (seed=2): `reacquisition_time`
- **S13_all_disturbances** (seed=2): `acquisition_time`, `tracking_error`, `target_loss_rate`, `reacquisition_time`
- **S14_multi_target** (seed=1): `reacquisition_time`
- **S14_multi_target** (seed=2): `reacquisition_time`
- **S15_slew10** (seed=1): `acquisition_time`, `tracking_error`, `target_loss_rate`, `reacquisition_time`
- **S15_slew10** (seed=2): `acquisition_time`, `tracking_error`, `target_loss_rate`, `reacquisition_time`

## Provenance

- Report generated: `2026-09-30T10:13:12.802352+00:00`
- SkyLock version: `0.1.0`
- Total JSON run files: `30`
- Scenarios with NOT_RUN status: `0`

---
*This report was generated by `scripts/gen_validation_report.py`. Do not hand-edit numbers.*