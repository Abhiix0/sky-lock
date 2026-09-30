# SkyLock Configuration Specification

**Document ID:** `DOC-CONFIG-001`  
**Classification:** Authoritative Configuration Reference  
**Applicability:** SkyLock Python Rebuild (Phase 1+)

---

## 1. Overview & Architectural Principles

1. **Single Authoritative Tree:** All runtime parameters descend from `skylock.config.models.SkyLockConfig`.
2. **Immutability & Safety:** All configuration models are `@dataclass(frozen=True, slots=True)` instances. Modifying fields in-place is prohibited; overrides use `skylock.config.io.override()` (built on `dataclasses.replace`) which re-validates the entire configuration tree.
3. **No Global State:** No module in `skylock` creates module-level default configuration instances. Component instances receive their respective configuration models in their `__init__` constructor.
4. **Validation Aggregation:** `ConfigError` aggregates **all** schema and cross-field violations across sections into a single exception rather than failing at the first error encountered.
5. **Determinism:** `config_hash(cfg)` calculates the canonical SHA-256 hash of the configuration to guarantee run reproducibility.

---

## 2. Configuration Schema & Parameter Reference

### 2.1 Camera (`camera: CameraConfig`)

| Field | Type | Default | Range / Allowed | PS_SPEC Ref | Description |
|---|---|---|---|---|---|
| `width` | `int` | `640` | `[32, inf)` | §2 | Sensor horizontal resolution (pixels) |
| `height` | `int` | `480` | `[32, inf)` | §2 | Sensor vertical resolution (pixels) |
| `fov_h_deg` | `float` | `4.0` | `(0, 180)` | §1 | Horizontal field of view in degrees |
| `fov_v_deg` | `float` | `3.0` | `(0, 180)` | §1 | Vertical field of view in degrees |
| `fps` | `float` | `30.0` | `[30.0, inf)` | §2 | Minimum sensor frame rate (Hz) |
| `monochrome` | `bool` | `True` | `{True, False}` | §2 | Monochrome focal plane array |
| `bit_depth` | `int` | `8` | `{8, 16}` | §2 | Pixel depth |
| `background_level` | `float` | `20.0` | `[0.0, 255.0]` | Sim | Baseline dark sensor level (grey levels) |
| `allow_below_spec_fps` | `bool` | `False` | `{True, False}` | — | Test-only escape hatch to permit `fps < 30.0` |

**Derived Read-Only Properties:**
- `ifov_h_deg`: `fov_h_deg / width` (`0.00625°/px` at default).
- `ifov_v_deg`: `fov_v_deg / height` (`0.00625°/px` at default).
- `frame_period_s`: `1.0 / fps` (`0.0333... s` at 30 Hz).
- `px_per_deg`: `width / fov_h_deg` (`160.0 px/deg` at default).
- **Square-pixel check:** `|ifov_h_deg - ifov_v_deg| / ifov_h_deg <= 0.01` (1% tolerance enforced).

---

### 2.2 Gimbal (`gimbal: GimbalConfig`)

| Field | Type | Default | Range / Allowed | PS_SPEC Ref | Description |
|---|---|---|---|---|---|
| `slew_rate_deg_s` | `float` | `5.0` | `(0, max_slew_rate]` | §3 | Default tracking slew rate (deg/s) |
| `max_slew_rate_deg_s` | `float` | `10.0` | `(0, 10.0]` | §3 | Maximum physical slew rate (deg/s) |
| `accel_deg_s2` | `float` | `120.0` | `(0, inf)` | Dynamics | Maximum gimbal acceleration (deg/s²) |
| `pan_limit_deg` | `tuple[float, float]` | `(-45.0, 45.0)` | `min < max` | — | Pan travel limits (azimuth) |
| `tilt_limit_deg` | `tuple[float, float]` | `(-30.0, 30.0)` | `min < max` | — | Tilt travel limits (elevation) |
| `initial` | `tuple[float, float]` | `(0.0, 0.0)` | Within limits | — | Initial pan/tilt pointing (deg) |
| `substeps` | `int` | `4` | `[1, inf)` | Sim | Numerical integration substeps per frame |

---

### 2.3 Target & Motion (`target: TargetSetConfig`)

Contains `count: int` and a tuple of `TargetConfig` items.

#### `TargetConfig`:
| Field | Type | Default | Range / Allowed | PS_SPEC Ref | Description |
|---|---|---|---|---|---|
| `id` | `str` | `"target_0"` | Non-empty | — | Unique target identifier |
| `size_px` | `int` | `10` | `[5, 20]` (or `[1, inf)` if `strict_spec=False`) | §4 | Optical beacon spot dimension (px) |
| `shape` | `str` | `"disc"` | `square`, `disc`, `gaussian`, `cross`, `custom_mask` | §4 | Target shape geometry |
| `brightness` | `float` | `220.0` | `(0, 255]` | — | Peak spot brightness (greyscale level) |
| `initial` | `str` | `"random"` | `"random"`, `"fixed"` | §4 | Initial placement policy |
| `initial_pos_deg` | `tuple[float, float]` | `(0.0, 0.0)` | Within limits | — | Position when `initial="fixed"` |
| `motion` | `MotionConfig` | `LineMotion()` | Union of motion types | §5 | Kinematic trajectory model |
| `visibility_windows` | `tuple[tuple[float, float], ...]` | `()` | `0 <= t0 <= t1` | — | Beacon blanking/occlusion periods |
| `strict_spec` | `bool` | `True` | `{True, False}` | — | Enforce 5–20 px size rule |

#### Motion Models (`motion: MotionConfig`):
1. `LineMotion(speed_deg_s=0.5, heading_deg=0.0)`
2. `CircleMotion(radius_deg=1.0, period_s=10.0, phase_rad=0.0)`
3. `Figure8Motion(width_deg=1.5, height_deg=1.0, period_s=12.0)`
4. `RandomMotion(speed_deg_s=0.5, correlation_s=2.0, bounds_deg=(-1.5, 1.5, -1.0, 1.0))`

---

### 2.4 Detection (`detection: DetectionConfig`)

| Field | Type | Default | Range / Allowed | Description |
|---|---|---|---|---|
| `method` | `str` | `"classical"` | `"classical"` | Detection pipeline algorithm |
| `blur_sigma` | `float` | `1.0` | `[0, inf)` | Gaussian pre-filter smoothing radius |
| `threshold_k_sigma` | `float` | `5.0` | `(0, inf)` | Adaptive threshold multiplier above noise |
| `abs_min_threshold` | `float` | `25.0` | `[0, 255]` | Hard minimum grey-level cutoff |
| `min_area_px` | `int` | `6` | `[1, inf)` | Minimum connected component area |
| `max_area_px` | `int` | `900` | `[min_area_px, inf)`| Maximum connected component area |
| `max_blobs` | `int` | `8` | `[1, inf)` | Maximum candidate detections returned |
| `roi_margin_px` | `int` | `48` | `[0, inf)` | Cropping window margin around track estimate |
| `median_filter` | `bool` | `True` | `{True, False}` | Salt & pepper noise pre-suppression |

---

### 2.5 Tracking (`tracking: TrackingConfig`)

| Field | Type | Default | Range / Allowed | PS_SPEC Ref | Description |
|---|---|---|---|---|---|
| `confirm_hits` | `int` | `3` | `[1, confirm_window]` | — | M-of-N hits required to acquire |
| `confirm_window` | `int` | `5` | `[confirm_hits, inf)` | — | M-of-N sliding window frame count |
| `acquire_timeout_s` | `float` | `1.0` | `(0, req.acquisition_max_s]` | §7 | Time limit before aborting ACQUIRE |
| `lost_after_misses` | `int` | `5` | `[1, inf)` | — | Consecutive misses before entering LOST |
| `coast_max_s` | `float` | `0.5` | `[0, inf)` | — | Duration to coast on Kalman prediction |
| `reacquire_timeout_s` | `float` | `1.0` | `(0, req.reacquisition_max_s]` | §7 | Spiral search timeout in REACQUIRE |
| `reacquire_radius_deg` | `float` | `1.0` | `(0, inf)` | — | Maximum spiral search radius |
| `association_gate_px` | `float` | `30.0` | `[target.size_px, inf)` | — | Spatial gating threshold for detection matching |
| `kalman` | `KalmanConfig` | `q=25.0, r=1.0, gate=4.0` | — | — | 4-state constant-velocity filter parameters |
| `search` | `SearchConfig` | `field=(10,8), scan_rate=4.0` | `scan_rate <= slew_rate` | — | Raster scan search pattern parameters |

---

### 2.6 Pointing Controller (`control: ControlConfig`)

| Field | Type | Default | Range / Allowed | Description |
|---|---|---|---|---|
| `kp` | `float` | `4.0` | `[0, inf)` | Proportional gain |
| `ki` | `float` | `0.5` | `[0, inf)` | Integral gain |
| `kd` | `float` | `0.2` | `[0, inf)` | Derivative gain |
| `kff` | `float` | `1.0` | `[0, inf)` | Velocity feed-forward gain |
| `d_filter_alpha` | `float` | `0.2` | `[0, 1]` | Derivative low-pass filter smoothing |
| `integral_clamp` | `float` | `8.0` | `[0, inf)` | Anti-windup rate clamp (deg/s) |
| `deadband_px` | `float` | `1.0` | `[0, req.lock_radius_px)` | Inner pixel deadband to prevent chatter |
| `latency_frames` | `int` | `1` | `[0, inf)` | Transport delay from computation to actuation |
| `mode` | `str` | `"AUTO"` | `"AUTO"`, `"MANUAL"` | Autonomous tracking or manual pointing |

---

### 2.7 Environmental Disturbances (`disturbances: DisturbanceConfig`)

Each disturbance is independently toggled and parameterized:

> [!IMPORTANT]
> **Interpretation of "Noise σ Maximum 20 px" (PS_SPEC §6):**
> In optical sensor and imaging specifications, camera noise standard deviation ($\sigma$) represents intensity fluctuations on the sensor focal plane array (measured in **grey levels** out of 255 for an 8-bit sensor). It is validated and clamped to `0 <= sigma_levels <= 20.0`. Spatial jitter and platform vibrations are modeled separately as `camera_jitter` and `platform` motions, each clamped to `|offset| <= 20.0 px/frame`.

| Component | Key Parameters | Limits / Bounds | PS_SPEC Ref |
|---|---|---|---|
| `salt_pepper` | `enabled: bool`, `density: float` | `density in [0, 1]` | §6 |
| `gaussian` | `enabled: bool`, `sigma_levels: float` | `sigma_levels in [0, 20.0]` | §6 (interpreted as grey levels) |
| `poisson` | `enabled: bool`, `photon_scale: float` | `photon_scale > 0` | §6 |
| `camera_jitter` | `enabled: bool`, `max_px_frame: float`, `correlation: float` | `|max_px_frame| <= 20.0`, `correlation in [0, 1]` | §6 |
| `platform` | `enabled: bool`, `kind: str`, `velocity_px_frame: float`, `max_px_frame: float` | `|velocity| <= 20.0`, `|max_px| <= 20.0` | §6 (linear platform motion) |
| `atmosphere` | `enabled: bool`, `mode: str`, `strength: float` | `mode in ('clear','haze','fog','rain','low_light')`, `strength in [0, 1]` | §6 |
| `blur` | `enabled: bool`, `sigma_px: float` | `sigma_px >= 0` | Optical defocus / seeing |

---

### 2.8 Requirements (`requirements: RequirementsConfig`)

Authoritative benchmark thresholds (the only place performance numbers appear; tracking logic does not use these directly, only validates against them):

| Requirement | Value | PS_SPEC Ref | Description |
|---|---|---|---|
| `acquisition_max_s` | `2.0 s` | §7 | Maximum allowable time to initial lock |
| `tracking_error_px_max` | `10.0 px` | §7 | Maximum allowable RMS boresight error |
| `tracking_error_statistic`| `"rms"` | §7 | Metric calculation method |
| `target_loss_rate_max` | `0.05 (5%)`| §7 | Maximum ratio of frames in LOST/REACQUIRE |
| `reacquisition_max_s` | `1.0 s` | §7 | Maximum time to recover lock after occlusion |
| `processing_fps_min` | `20.0 FPS`| §7 | Minimum throughput cadence |
| `lock_radius_px` | `10.0 px` | §7 | Threshold defining in-track lock |

---

### 2.9 Cross-Field Constraints

1. **Target Size vs Camera Sensor:**
   $$\forall i, \quad \text{target.size\_px}_i < \frac{\min(\text{width}, \text{height})}{4}$$
2. **Gating vs Target Size:**
   $$\text{tracking.association\_gate\_px} \ge 2 \times \frac{\text{primary\_target.size\_px}}{2} = \text{primary\_target.size\_px}$$
3. **Scan Rate vs Gimbal Slew:**
   $$\text{tracking.search.scan\_rate\_deg\_s} \le \text{gimbal.slew\_rate\_deg\_s}$$
4. **Acquisition Timing:**
   $$\text{tracking.acquire\_timeout\_s} \le \text{requirements.acquisition\_max\_s} \quad (1.0\,\text{s} \le 2.0\,\text{s})$$
5. **Re-acquisition Timing:**
   $$\text{tracking.reacquire\_timeout\_s} \le \text{requirements.reacquisition\_max\_s} \quad (1.0\,\text{s} \le 1.0\,\text{s})$$
6. **Controller Deadband vs Lock Threshold:**
   $$\text{control.deadband\_px} < \text{requirements.lock\_radius\_px} \quad (1.0\,\text{px} < 10.0\,\text{px})$$
