# SkyLock Pointing Controller: Classical Control Design & Stability Analysis

## 1. System Dynamics & Plant Model

The SkyLock closed-loop tracking loop controls a two-axis (pan and tilt) gimbal plant driven by angular rate commands.

### 1.1 Plant Transfer Function
The gimbal acts as an angular rate actuator: commanding an angular rate $\dot{\theta}_{cmd}$ drives gimbal velocity towards the command under acceleration limits ($a_{max} = 120^\circ/\text{s}^2$). For operating bandwidths ($\omega < 10$ rad/s), acceleration dynamics are fast relative to the loop response, yielding a pure integrator transfer function from rate command to pointing angle:

$$G_p(s) = \frac{\theta(s)}{\dot{\theta}(s)} = \frac{1}{s}$$

### 1.2 Measurement and Error Conversion
Target tracking error is measured in camera focal plane coordinates:
$$e_{px} = (x_{target} - x_{boresight}, y_{target} - y_{boresight})$$

Using the camera Instantaneous Field of View ($\text{IFOV} = 0.00625^\circ/\text{px}$ for a $4.0^\circ \times 3.0^\circ$ FOV at $640 \times 480$), the error is converted to angular space:
$$\theta_{err, pan} = e_x \cdot \text{IFOV}_h$$
$$\theta_{err, tilt} = -e_y \cdot \text{IFOV}_v$$

### 1.3 Transport Delay (Latency)
Sensor capture, exposure, readout, and pipeline processing introduce a discrete 1-frame transport delay:
$$T_d = \frac{1}{f_{fps}} = \frac{1}{30.0} \approx 0.0333\text{ s}$$

In the continuous Laplace domain, this is modeled by:
$$G_d(s) = e^{-s T_d}$$

---

## 2. PID Controller Architecture

The feedback controller generates commanded rate $\dot{\theta}_{pid}$ using a filtered PID structure with conditional integration anti-windup:

$$C(s) = K_p + \frac{K_i}{s} + \frac{K_d s}{1 + s \tau_f}$$

### 2.1 Velocity Feedforward
To eliminate steady-state lag during constant-velocity target motion (such as aircraft crossing the sensor at $0.2^\circ/\text{s} - 1.0^\circ/\text{s}$), the controller incorporates velocity feedforward from the Kalman state estimate:
$$\dot{\theta}_{cmd} = \dot{\theta}_{pid} + K_{ff} \cdot \hat{\dot{\theta}}_{target}$$
With $K_{ff} = 1.0$, the feedforward term directly supplies the nominal target rate, reducing the feedback loop's burden to disturbance rejection and residual estimation errors.

---

## 3. Stability Margin Derivation

The open-loop transfer function of the uncompensated loop with pure proportional feedback $K_p$ is:
$$L(s) = K_p \cdot \frac{1}{s} \cdot e^{-s T_d}$$

### 3.1 Gain Crossover Frequency $\omega_c$
At the gain crossover frequency $\omega_c$, $|L(j\omega_c)| = 1$:
$$\frac{K_p}{\omega_c} = 1 \implies \omega_c = K_p$$

Choosing $\omega_c = 4.0\text{ rad/s}$ ($f_c \approx 0.64\text{ Hz}$):
- Gain $K_p = 4.0\text{ s}^{-1}$
- Loop response time $\tau \approx 1/\omega_c = 0.25\text{ s}$ (settles well within the $2.0\text{ s}$ requirement).

### 3.2 Phase Margin Calculation
The phase contribution of each component at $\omega_c = 4.0\text{ rad/s}$:
1. **Integrator plant ($1/s$):** $\phi_{plant} = -90^\circ$
2. **Transport delay ($e^{-j \omega T_d}$):**
   $$\phi_{delay} = -\omega_c T_d = -4.0 \times \frac{1}{30} = -0.1333\text{ rad} \approx -7.64^\circ$$
3. **Integral action ($K_i = 0.5$):**
   $$\Delta \phi_i = -\arctan\left(\frac{K_i}{\omega_c K_p}\right) = -\arctan\left(\frac{0.5}{16.0}\right) \approx -1.79^\circ$$
4. **Derivative action ($K_d = 0.2$):**
   $$\Delta \phi_d = +\arctan\left(\frac{\omega_c K_d}{K_p}\right) = +\arctan\left(\frac{0.8}{4.0}\right) \approx +11.31^\circ$$

Total open-loop phase at crossover:
$$\phi_{OL}(\omega_c) = -90^\circ - 7.64^\circ - 1.79^\circ + 11.31^\circ = -88.12^\circ$$

The resulting **Phase Margin (PM)** is:
$$\text{PM} = 180^\circ + \phi_{OL}(\omega_c) = 180^\circ - 88.12^\circ = \mathbf{91.88^\circ}$$

A phase margin of $\approx 92^\circ$ (substantially higher than the standard $60^\circ$ benchmark) provides critical robustness against sensor noise, latency jitter, and unmodeled actuator dynamics.

### 3.3 Gain Margin Calculation
The phase crossover frequency $\omega_\pi$ occurs where total phase is $-180^\circ$:
$$-90^\circ - \omega_\pi T_d = -180^\circ \implies \omega_\pi T_d = \frac{\pi}{2}$$
$$\omega_\pi = \frac{\pi}{2 T_d} = \frac{\pi}{2 \times (1/30)} = 15\pi \approx 47.12\text{ rad/s}$$

The loop gain at $\omega_\pi$ is:
$$|L(j\omega_\pi)| = \frac{K_p}{\omega_\pi} = \frac{4.0}{47.12} \approx 0.0849$$

The **Gain Margin (GM)** is:
$$\text{GM} = 20 \log_{10}\left(\frac{1}{|L(j\omega_\pi)|}\right) = 20 \log_{10}(11.78) = \mathbf{+21.4\text{ dB}}$$

A gain margin of $+21.4\text{ dB}$ (well exceeding the standard $10\text{ dB}$ requirement) guarantees unconditional loop stability under gain variations.

---

## 4. Parameter Summary

| Parameter | Value | Unit | Rationale |
|---|---|---|---|
| $K_p$ | 4.0 | $\text{s}^{-1}$ | Yields $\omega_c = 4.0$ rad/s, settling in $< 1$ s with $> 80^\circ$ PM |
| $K_i$ | 0.5 | $\text{s}^{-2}$ | Eliminates steady-state offset without causing windup or phase loss ($< 2^\circ$) |
| $K_d$ | 0.2 | s | Provides $+11^\circ$ phase lead at crossover to damp gimbal acceleration |
| $K_{ff}$ | 1.0 | unitless | Direct velocity feedforward to cancel constant-velocity target lag |
| $d\_filter\_alpha$ | 0.8 | unitless | First-order low-pass filter on derivative ($\tau_f \approx 0.0083$ s) to attenuate pixel quantization noise |
| $integral\_clamp$ | 2.0 | $^\circ/\text{s}$ | Limits integrator contribution to $\le 20\%$ of maximum actuator slew rate |
| $deadband\_px$ | 0.5 | px | Suppresses limit-cycle hunting due to subpixel centroid quantization |
