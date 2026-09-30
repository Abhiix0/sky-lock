# Sky Lock Performance Metrics Specification

This document provides formal mathematical definitions for all tracking, optical, servo, and algorithm latency metrics computed by `src/tracking/metrics.js`.

---

## 1. Observability (`observable(t)`)

A target is defined as **observable** at simulation time $t$ if and only if:
1. **Line-of-Sight Clear**: The optical ray between observer and target is unoccluded by Earth's planetary sphere ($R_{\text{Earth}} = 10.0$ scene units).
2. **Kinematically Reachable**: The line-of-sight vector lies within the mechanical angular limits of the two-axis gimbal:
   $$\text{pan} \in [-180^\circ, +180^\circ], \quad \text{tilt} \in [-90^\circ, +90^\circ]$$

$$\text{observable}(t) = \text{losClear}(t) \land \text{isReachable}(t)$$

Total observable duration over a test span:
$$T_{\text{obs}} = \int_{0}^{T} \mathbf{1}_{\{\text{observable}(t)\}} \, dt$$

---

## 2. Acquisition Time

- **First Observable Instant ($t_0$)**: The earliest timestamp $t \ge 0$ where $\text{observable}(t) = \text{true}$.
- **First Track Instant ($t_{\text{track}}$)**: The earliest timestamp where the autonomous acquisition state machine transitions to `TRACK`.

$$\Delta t_{\text{acq}} = t_{\text{track}} - t_0$$

We also record time elapsed from scenario start:
$$\Delta t_{\text{acq,start}} = t_{\text{track}}$$

---

## 3. Reacquisition Time (Per Occlusion)

When the line-of-sight is blocked by Earth, the target becomes unobservable ($\text{observable}(t) = \text{false}$) and the state machine enters `LOST` $\to$ `REACQUIRE`.
Upon target emergence:
- $t_{\text{emerge}, i}$: Timestamp where $\text{observable}(t)$ transitions from `false` to `true` for occlusion event $i$.
- $t_{\text{retrack}, i}$: Timestamp where the state machine re-enters `TRACK`.

$$\Delta t_{\text{reacq}, i} = t_{\text{retrack}, i} - t_{\text{emerge}, i}$$

The metrics module reports:
- List of individual reacquisition times $\{\Delta t_{\text{reacq}, i}\}$
- Mean reacquisition time: $\overline{\Delta t}_{\text{reacq}}$
- Maximum reacquisition time: $\max(\Delta t_{\text{reacq}, i})$

---

## 4. Pointing & Tracking Errors

Let $(x_c, y_c) = (W/2, H/2) = (320, 240)$ be the camera frame principal optical center.
Let $(x_{\text{gt}}, y_{\text{gt}})$ be the ground-truth projection of the beacon on the image sensor.
Let $(x_{\text{est}}, y_{\text{est}})$ be the Kalman state estimate projected into camera pixel coordinates.

### Pointing Error ($e_{\text{point}}$)
The Euclidean offset from the sensor center to the true target, evaluated while `observable(t)` and state is `TRACK`:
$$e_{\text{point}}(t) = \sqrt{(x_{\text{gt}}(t) - x_c)^2 + (y_{\text{gt}}(t) - y_c)^2} \quad \text{[pixels]}$$

### Tracking Error ($e_{\text{track}}$)
The Euclidean offset between the Kalman filter estimate and ground-truth beacon position:
$$e_{\text{track}}(t) = \sqrt{(x_{\text{gt}}(t) - x_{\text{est}}(t))^2 + (y_{\text{gt}}(t) - y_{\text{est}}(t))^2} \quad \text{[pixels]}$$

### Milliradian Conversion
Given camera vertical field of view $\theta_{\text{fov}} = 12^\circ$ and frame height $H = 480\text{ px}$:
$$k_{\text{mrad/px}} = \frac{\theta_{\text{fov}} \cdot \frac{\pi}{180^\circ}}{H} \times 1000 \approx 0.436332 \text{ mrad/px}$$
$$e_{\text{mrad}} = e_{\text{px}} \times k_{\text{mrad/px}}$$

### Summary Statistics
For both pointing and tracking error over all $N$ valid in-track samples:
- **Mean**: $\mu = \frac{1}{N} \sum e_k$
- **RMS**: $\text{RMS} = \sqrt{\frac{1}{N} \sum e_k^2}$
- **Max**: $\max(e_k)$
- **95th Percentile ($p_{95}$)**: The value below which 95% of observations fall.

---

## 5. Lock Retention Rate

The fraction of observable time during which the tracker maintains `TRACK` state with pointing error within the calibrated optical link lock radius ($r_{\text{lock}} = 30\text{ px}$):

$$R_{\text{lock}} = \frac{1}{T_{\text{obs}}} \int_{0}^{T} \mathbf{1}_{\{\text{state}(t) = \text{'TRACK'} \;\land\; e_{\text{point}}(t) < r_{\text{lock}}\}} \, dt \times 100\%$$

---

## 6. False Locks

A **false lock** is defined as an interval where the state machine remains in `TRACK` for greater than $1.0\text{ s}$ while the estimated pointing is separated from ground truth by more than $r_{\text{false}} = 50\text{ px}$:

$$\text{FalseLockSpan} \iff \text{duration}\Big(\{t \mid \text{state}(t) = \text{'TRACK'} \;\land\; e_{\text{point}}(t) > r_{\text{false}}\}\Big) > 1.0\text{ s}$$

Each contiguous span satisfying this criterion increments the false lock counter by 1.

---

## 7. Computational Latency & Frame Rate

- **Processing Time per Frame**: Latency $t_{\text{proc}}$ measured from frame receipt through sensor disturbance processing, blob detection, candidate tracking, beacon ID, and state update.
  - Mean latency ($\text{ms}$)
  - 95th percentile latency $p_{95}$ ($\text{ms}$)
  - Maximum latency ($\text{ms}$)
- **Render FPS**: Frame rate computed over rolling 500 ms windows:
  - Mean FPS
  - Minimum instantaneous FPS
- **Dropped Feed Frames**: Cumulative count of camera feed frames dropped by the disturbance layer ($p_{\text{drop}}$).
