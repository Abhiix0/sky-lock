# SkyLock Performance Metrics Specification & Normative Definitions

**Document ID:** `DOC-METRICS-001`  
**Classification:** Authoritative Technical Metric Specification  
**Version:** `1` (Normative)  
**Target System:** SkyLock Optical Tracking Rebuild  

---

## 1. Overview & Measurement Semantics

SkyLock adopts explicit, honest performance metrics wrapped in the `Metric[T]` contract. No unmeasured metric may ever silently default to `0`, `60`, or `1.0`.

### 1.1 Invariant Contract

Every metric reports one of four unambiguous statuses defined in `skylock.core.enums.MetricStatus`:

| Status | Meaning | Invariant on `value` |
|---|---|---|
| `MEASURED` | Metric was computed from valid, verified observations. | `value is not None` (and non-NaN) |
| `NOT_RUN` | Prerequisite observations or ground truth were absent. | `value is None` |
| `NOT_ACQUIRED` | Target was never acquired or locked during the run. | `value is None` |
| `FAILED` | Process aborted, deadline failed, or recovery failed. | `value is None` |

When serialized to JSON, any non-`MEASURED` metric emits `null`, never `NaN` or a synthetic placeholder.

---

## 2. Metric Definitions & Formulas

### 2.1 Acquisition Time (`acquisition_time_s`)

The time elapsed between a reference epoch and the earliest frame index $k_{\text{track}}$ where the tracking state machine transitions to `TrackState.TRACK`.

1. **`from_start`**:
   $$\Delta t_{\text{acq,start}} = t[k_{\text{track}}] - t[0]$$
   - Computable without ground truth (e.g., MP4 external video).
   - If `TRACK` is never reached: `NOT_ACQUIRED`.

2. **`from_first_observable`**:
   $$\Delta t_{\text{acq,obs}} = t[k_{\text{track}}] - t[k_{\text{first\_obs}}]$$
   where $k_{\text{first\_obs}}$ is the earliest frame where ground-truth beacon visibility is `True`.
   - Requires ground-truth visibility. If ground truth is absent: `NOT_RUN` with reason `"Requires ground truth target visibility"`.
   - If `TRACK` is never reached: `NOT_ACQUIRED`.

3. **`successful_acquisition`**:
   `Metric[bool]`: `MEASURED(True)` if acquired, `NOT_ACQUIRED` if never reached `TRACK`.

### 2.2 Spatial Errors

Let $(x_c, y_c) = (W/2, H/2)$ be the camera principal optical center (boresight).  
Let $(x_{\text{gt}}, y_{\text{gt}})$ be the ground-truth beacon coordinates.  
Let $(x_{\text{est}}, y_{\text{est}})$ be the filtered target kinematic estimate.

Each error metric aggregates over valid frames $k$ producing an `ErrorStats` record:
- **Mean:** $\mu = \frac{1}{N} \sum e_k$
- **RMS:** $\text{RMS} = \sqrt{\frac{1}{N} \sum e_k^2}$
- **95th Percentile ($p_{95}$):** Empirical 95th percentile.
- **Max:** $\max(e_k)$
- **Sample Count ($n$):** $N$

#### 1. Tracking Error (`tracking_error_px`)
Evaluated strictly over frames where $\text{state}[k] == \text{TRACK}$ and $\text{target.visible}[k] == \text{True}$:
$$e_{\text{track}}[k] = \sqrt{(x_{\text{est}}[k] - x_{\text{gt}}[k])^2 + (y_{\text{est}}[k] - y_{\text{gt}}[k])^2}$$
- Requires ground truth. If absent: `NOT_RUN`.

#### 2. Pointing Error (`pointing_error_px`)
Evaluated strictly over frames where $\text{state}[k] == \text{TRACK}$ and $\text{target.visible}[k] == \text{True}$:
$$e_{\text{point}}[k] = \sqrt{(x_{\text{gt}}[k] - x_c)^2 + (y_{\text{gt}}[k] - y_c)^2}$$
- Requires ground truth. If absent: `NOT_RUN`.

#### 3. Centering Error (`centering_error_px`)
Evaluated over frames where $\text{state}[k] == \text{TRACK}$ and an estimate exists:
$$e_{\text{center}}[k] = \sqrt{(x_{\text{est}}[k] - x_c)^2 + (y_{\text{est}}[k] - y_c)^2}$$
- Purely estimate-driven. Fully measurable for external MP4 video feeds without ground truth.

### 2.3 Reacquisition Time (`reacquisition_time_s`)

Measures the responsiveness of the system recovering track following an interruption or occlusion event.

- **Ground Truth Basis (when GT is available):**
  Triggered when target visibility transitions from `True` $\to$ `False` (occlusion) and subsequently emerges `False` $\to$ `True` at $t_{\text{reappear}}$.
  $$\Delta t_{\text{reacq}} = t_{\text{retrack}} - t_{\text{reappear}}$$
- **Tracker-Only Basis (when GT is unavailable):**
  Triggered when tracker state machine transitions into `LOST` at $t_{\text{loss}}$ and subsequently re-enters `TRACK` at $t_{\text{retrack}}$:
  $$\Delta t_{\text{reacq}} = t_{\text{retrack}} - t_{\text{loss}}$$
  Flagged explicitly with `basis = "tracker_only"`.

- **Event Outcomes:**
  - If no loss events occurred: `NOT_RUN` ("No loss event occurred").
  - If target emerged/lost and never recovered to `TRACK`: `FAILED` ("Target loss event never recovered to TRACK").
  - `successful_reacquisition`: `MEASURED(True)` if all reacquisition events satisfied $\Delta t \le \text{reacquire\_max\_s}$; `MEASURED(False)` if any event failed or unrecovered; `NOT_RUN` if no loss events occurred.

### 2.4 Target Loss Rate (`target_loss_rate`)

The fraction of frames following the initial `TRACK` acquisition during which the tracker is not in `TRACK`:
$$R_{\text{loss}} = \frac{\sum_{k=k_{\text{first\_track}}}^{N-1} \mathbf{1}_{\{\text{state}[k] \ne \text{TRACK}\}}}{N - k_{\text{first\_track}}}$$
- If never acquired: `NOT_ACQUIRED`.

### 2.5 Lock Retention (`lock_retention`)

The fraction of post-acquisition frames where the tracker is in `TRACK` and error is contained within $r_{\text{lock}}$ (`cfg.requirements.lock_radius_px`):
$$R_{\text{lock}} = \frac{\sum_{k=k_{\text{first\_track}}}^{N-1} \mathbf{1}_{\{\text{state}[k] = \text{TRACK} \;\land\; e[k] \le r_{\text{lock}}\}}}{N - k_{\text{first\_track}}}$$
- Uses $e_{\text{point}}$ when ground truth is available; uses $e_{\text{center}}$ when evaluating without ground truth.
- If never acquired: `NOT_ACQUIRED`.

### 2.6 Detection Rates

1. **`detection_rate`**:
   Fraction of ground-truth visible frames that contain at least one blob detection within the spatial association gate ($\le \text{gate}$):
   $$\text{Rate}_{\text{det}} = \frac{\sum_{k \in \text{Visible}} \mathbf{1}_{\{\exists d \in \text{detections}[k] \mid \|d - \text{gt}\| \le \text{gate}\}}}{|\text{Visible}|}$$
   - Requires ground truth; else `NOT_RUN`.

2. **`detection_present_rate`**:
   Fraction of total processed frames containing at least one detection (estimate/input-only, no GT required).

### 2.7 Cadence & Latency

1. **`fps_pipeline`**:
   $$f_{\text{pipe}} = \frac{N}{\sum_{k=0}^{N-1} t_{\text{latency}}[k]}$$
2. **`fps_wall`**:
   $$f_{\text{wall}} = \frac{N}{t_{\text{wall\_elapsed}}}$$
3. **`latency_ms`**:
   Summary statistics (`mean`, `p50`, `p95`, `max`, `n`) across all per-frame processing latencies.
4. **`missed_frames`**:
   Count of frames where processing latency exceeded the nominal frame period ($1 / f_{\text{nominal}}$). Source dropped frames are counted separately.

---

## 3. Requirement Evaluation & Tri-State Verdicts

Evaluated by `skylock.metrics.requirements.evaluate(run_metrics, cfg.requirements)`.

### 3.1 Verdict Criteria (PS_SPEC §7)

| Requirement | Threshold | Evaluated Metric |
|---|---|---|
| **Acquisition Time** | $\le 2.0\text{ s}$ | `acquisition_time_from_observable_s` |
| **Tracking Error** | $\le 10.0\text{ px}$ (RMS) | `tracking_error_px.rms` |
| **Target Loss Rate** | $< 0.05$ (5%) | `target_loss_rate` |
| **Reacquisition Time** | $\le 1.0\text{ s}$ | `reacquisition_time_s.max_s` |
| **Processing Cadence** | $\ge 20.0\text{ FPS}$ | `fps_pipeline` |

### 3.2 Verdict Rules

1. Any non-`MEASURED` required metric produces `Verdict.INDETERMINATE`. A non-measured metric **never** yields `Verdict.PASS`.
2. **Special Acquisition Rule:** Acquisition evaluates to `Verdict.FAIL` (not `INDETERMINATE`) if the run provided a full observable window ($\ge \text{acquisition\_max\_s}$) and the tracker never reached `TRACK`.
3. **Overall Verdict:**
   - `FAIL` if **any** requirement is `FAIL`.
   - `INDETERMINATE` if **any** requirement is `INDETERMINATE` and none is `FAIL`.
   - `PASS` only if **all** requirements are `PASS`.
