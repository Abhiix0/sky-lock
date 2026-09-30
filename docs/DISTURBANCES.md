# Environmental and Sensor Disturbance Specifications

**Document ID:** `DOC-DISTURBANCES-001`  
**Classification:** Authoritative Technical Specification & Mathematical Reference  
**Target System:** Sky Lock Simulation Subsystem  
**Specification Baseline:** `PS_SPEC.md` Section 6  

---

## 1. Pipeline Execution Architecture

Disturbances in SkyLock are decoupled into two distinct categories: **Geometric Perturbations** (line-of-sight pointing displacements) and **Photometric Degradations** (focal-plane sensor image corruption).

```
[Simulation Time t, Frame k]
           │
           ├──► Geometric Disturbances
           │      ├─ Camera Jitter (AR(1) LOS Vibration)
           │      └─ Platform Motion (Linear Accumulated Drift)
           │      ▼
           │    Aggregate Offset (dx, dy) 
           │           │
           │           ▼
           ├─────► VirtualCamera.render(pointing, extra_offset_px=(dx, dy))
           │           │
           │           ├─► GroundTruthSample (records (dx, dy) & post-offset true pixels)
           │           ▼
           │      image_float32 (clean rendered focal plane [0.0, 255.0])
           │           │
           └──► Photometric Disturbances
                  ├─ 1. Atmosphere (Clear, Haze, Fog, Rain, Low-Light)
                  ├─ 2. Optical Blur (Defocus PSF via Gaussian filter)
                  ├─ 3. Poisson Shot Noise (Quantum photon statistics)
                  ├─ 4. Gaussian Read Noise (FPA thermal / amplifier noise)
                  ├─ 5. Salt & Pepper (Dead & saturated impulse pixels)
                  ▼
              Quantization (Round + Clip to uint8 [0, 255])
                  ▼
              Frame.image (Monochrome sensor frame with NO ground truth)
```

---

## 2. Geometric Disturbance Models

### 2.1 Camera Jitter (`CameraJitter`)
- **Module:** `skylock.simulation.disturbances.jitter`
- **Config:** `JitterConfig(enabled, max_px_frame, correlation)`
- **PRNG Stream Key:** `dist.camera_jitter`
- **Mathematical Formulation:**
  Discrete-time first-order autoregressive process (AR(1)) simulating mechanical gimbal vibration:
  $$\begin{aligned}
  x_0 &= \sigma \cdot w_{x, 0} \\
  x_k &= \rho x_{k-1} + \sqrt{1 - \rho^2} \cdot \sigma \cdot w_{x, k}, \quad w_{x, k} \sim \mathcal{N}(0, 1)
  \end{aligned}$$
  where $\rho = \text{correlation} \in [0, 1.0)$, and $\sigma = \text{max\_px\_frame}$.
  Hard runtime clipping guarantees compliance with `PS_SPEC §6`:
  $$dx_k = \text{clip}(x_k, -\text{max\_px\_frame}, +\text{max\_px\_frame})$$
  $$dy_k = \text{clip}(y_k, -\text{max\_px\_frame}, +\text{max\_px\_frame})$$
- **Units:** Pixels per frame ($|dx|, |dy| \le 20.0$ px/frame).
- **Invariance:** Sequential caching guarantees out-of-order queries return identical offsets.

### 2.2 Platform Motion (`PlatformMotion`)
- **Module:** `skylock.simulation.disturbances.platform`
- **Config:** `PlatformConfig(enabled, kind="linear", velocity_px_frame=(vx, vy), max_px_frame)`
- **PRNG Stream Key:** `dist.platform`
- **Mathematical Formulation:**
  Mandatory linear platform translation per `PS_SPEC §6`:
  $$\vec{v} = (v_x, v_y), \quad \|\vec{v}\| = \sqrt{v_x^2 + v_y^2}$$
  If $\|\vec{v}\| > \text{max\_limit}$ (where $\text{max\_limit} \le 20.0$ px/frame):
  $$\vec{v}_{\text{eff}} = \vec{v} \cdot \frac{\text{max\_limit}}{\|\vec{v}\|}$$
  Offset accumulates linearly across frames:
  $$\vec{D}_k = k \cdot \vec{v}_{\text{eff}}$$
- **Units:** Pixels ($k \times \text{px/frame}$).
- **Reset Behavior:** Resets accumulated position to $(0.0, 0.0)$.

---

## 3. Photometric Disturbance Models

### 3.1 Atmospheric Degradation (`Atmosphere`)
- **Module:** `skylock.simulation.disturbances.atmosphere`
- **Config:** `AtmosphereConfig(enabled, mode, strength)`
- **PRNG Stream Key:** `dist.atmosphere`
- **Modes & Formulations:**
  Let $I$ be the input float32 image and $B$ be the background black level ($B = 20.0$ grey levels), with strength $s \in [0, 1]$:
  1. **Clear:** Identity: $I_{\text{out}} = I$.
  2. **Haze:** Contrast compression toward background + additive airlight veil:
     $$I_{\text{out}} = B + (I - B) \cdot (1 - 0.5 s) + 30 s$$
  3. **Fog:** Stronger dynamic range attenuation + heavier veil + optical scattering blur ($\sigma \approx 1.0$ px):
     $$I_{\text{base}} = B + (I - B) \cdot (1 - 0.85 s) + 60 s$$
     $$I_{\text{out}} = \mathcal{G}_{\sigma=1.0}(I_{\text{base}})$$
  4. **Rain:** Atmospheric attenuation + semi-transparent seeded rain streak lines:
     $$I_{\text{att}} = B + (I - B) \cdot (1 - 0.15 s)$$
     $N = \lfloor 40 s \rfloor$ streaks drawn with angle $\theta \approx 75^\circ$, length $10\text{--}25$ px, color $B + 35 s$.
  5. **Low Light:** Optical signal attenuation with invariant sensor noise floor:
     $$I_{\text{out}} = B + (1 - 0.75 s) \cdot \max(0, I - B)$$
- **Contrast Ordering:** For identical scenes, $\text{Contrast}(\text{clear}) > \text{Contrast}(\text{haze}) > \text{Contrast}(\text{fog})$.

### 3.2 Optical Defocus Blur (`OpticalBlur`)
- **Module:** `skylock.simulation.disturbances.blur`
- **Config:** `BlurConfig(enabled, sigma_px)`
- **Mathematical Formulation:**
  Two-dimensional symmetric Gaussian Point Spread Function (PSF):
  $$I_{\text{out}} = I * \mathcal{K}_{\sigma}$$
  implemented via `cv2.GaussianBlur` with reflective border replication (`cv2.BORDER_REFLECT`).
- **Energy Preservation:** Total radiant energy $\sum_{x,y} I(x, y)$ is preserved within $< 0.01\%$.

### 3.3 Poisson Shot Noise (`PoissonNoise`)
- **Module:** `skylock.simulation.disturbances.noise`
- **Config:** `PoissonConfig(enabled, photon_scale)`
- **PRNG Stream Key:** `dist.poisson`
- **Mathematical Formulation:**
  Models discrete quantum photon arrivals on sensor pixels:
  $$\lambda = \max(0, I) \cdot s_{\text{photon}}$$
  $$N_{\text{photons}} \sim \text{Poisson}(\lambda)$$
  $$I_{\text{out}} = \frac{N_{\text{photons}}}{s_{\text{photon}}}$$
  Theoretical variance:
  $$\operatorname{Var}(I_{\text{out}}) = \frac{\lambda}{s_{\text{photon}}^2} = \frac{I}{s_{\text{photon}}}$$
- **High-Photon Fast Path:**
  For $\lambda > 50$, the Gaussian central limit theorem normal approximation is used:
  $$N_{\text{photons}} \approx \lambda + \sqrt{\lambda} \cdot \mathcal{N}(0, 1)$$
  This guarantees execution latency $\le 4.5$ ms at $640 \times 480$.

### 3.4 Gaussian Sensor Read Noise (`GaussianNoise`)
- **Module:** `skylock.simulation.disturbances.noise`
- **Config:** `GaussianConfig(enabled, sigma_levels)`
- **PRNG Stream Key:** `dist.gaussian`
- **Mathematical Formulation:**
  Additive white Gaussian noise modeling on-chip amplifier and thermal noise:
  $$I_{\text{out}} = I + \mathcal{N}(0, \sigma^2)$$
  $$\sigma = \min(20.0, \max(0.0, \sigma_{\text{levels}}))$$
- **Units:** Grey levels ($[0, 20.0]$ per `PS_SPEC §6`).

### 3.5 Salt & Pepper Impulse Noise (`SaltPepperNoise`)
- **Module:** `skylock.simulation.disturbances.noise`
- **Config:** `SaltPepperConfig(enabled, density)`
- **PRNG Stream Key:** `dist.salt_pepper`
- **Mathematical Formulation:**
  Independent pixel corruption with density $d \in [0, 1]$ drawn from $u \sim \mathcal{U}(0, 1)$:
  $$I_{\text{out}}(x, y) = \begin{cases}
  0.0 & u < d / 2 \quad (\text{pepper / dead pixel}) \\
  255.0 & d / 2 \le u < d \quad (\text{salt / saturated hot pixel}) \\
  I(x, y) & u \ge d
  \end{cases}$$

---

## 4. PRNG Derivation and Determinism

All PRNG instances are generated exclusively through `skylock.core.rng.derive_rng(seed, name)` using NumPy's `SeedSequence` hashing:
- Camera Jitter: `derive_rng(seed, "dist.camera_jitter")`
- Platform Motion: `derive_rng(seed, "dist.platform")`
- Atmosphere: `derive_rng(seed, "dist.atmosphere")`
- Optical Blur: `derive_rng(seed, "dist.blur")`
- Poisson Noise: `derive_rng(seed, "dist.poisson")`
- Gaussian Noise: `derive_rng(seed, "dist.gaussian")`
- Salt & Pepper: `derive_rng(seed, "dist.salt_pepper")`

### Stream Independence Guarantee
Because the spawn keys are derived from CRC32 hashes of the distinct component names:
1. Enabling or disabling any component consumes zero PRNG steps and does not affect the sequence of any other component.
2. Two simulation runs with the same root seed yield bit-identical frames across arbitrary frame lengths.
3. Invoking `SimulationSource.reset()` resets every component stream and exactly reproduces the identical frame sequence.

---

## 5. Measured Execution Performance (640 × 480 Frame)

Benchmarked on Windows with Python 3.12 (NumPy + OpenCV-headless):

| Component | Operation | Measured Execution Time |
|---|---|---|
| `CameraJitter` | AR(1) state step + clipping | **8.1 μs** |
| `PlatformMotion` | Linear translation step | **0.2 μs** |
| `Atmosphere (Haze)` | Contrast compression + veil | **1.24 ms** |
| `Atmosphere (Fog)` | Dynamic range scaling + Gaussian blur | **1.71 ms** |
| `Atmosphere (Rain)` | Attenuation + 40 vectorized streak draws | **1.12 ms** |
| `Atmosphere (Low-Light)` | Signal gain attenuation | **1.27 ms** |
| `OpticalBlur` | Reflective Gaussian PSF | **0.62 ms** |
| `GaussianNoise` | Additive $\mathcal{N}(0, \sigma^2)$ | **4.26 ms** |
| `SaltPepperNoise` | Uniform draw + mask replacement | **2.71 ms** |
| `PoissonNoise (Normal Approx)` | Vectorized quantum shot noise ($\lambda > 50$) | **4.46 ms** |
| `PoissonNoise (Exact Draw)` | NumPy exact Poisson draw ($\lambda \le 50$) | **16.7 ms** |
