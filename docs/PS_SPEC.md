# AUTHORITATIVE PS SPECIFICATION

**Document ID:** `DOC-PS-SPEC-001`  
**Classification:** Authoritative Technical Specification & Source of Truth  
**Target System:** Sky Lock — AI-Assisted Virtual Camera Tracking System for Mobile FSOC Terminal Coarse Alignment  
**Status:** Authoritative Baseline Active  

---

## 1. Field of View (FOV)
- **Horizontal FOV:** 4°
- **Vertical FOV:** 3°
- **Default FOV:** 4° × 3°

---

## 2. Camera Specification
- **Default Resolution:** 640 × 480 px
- **User-Definable Resolution:** Supported
- **Focal Plane Array:** Monochrome focal plane array
- **Minimum Camera Update Rate:** 30 Hz

---

## 3. Pan/Tilt Gimbal Slew Rates
- **Maximum Speed:** 5–10°/s
- **Default Speed:** 5°/s

---

## 4. Target Characteristics
- **Type:** Optical beacon spot
- **Target Count:** 1 mandatory target, multiple optional
- **Spot Size:** 5×5 to 20×20 px
- **Default Size:** 10×10 px
- **Target Shape:** User-defined shape supported
- **Initial Location:** Random initial location supported

---

## 5. Target Motion Models
- **Straight line**
- **Circular**
- **Figure-8**
- **Random**

---

## 6. Disturbances & Environmental Noise
- **Noise Types:**
  - Salt & pepper noise
  - Gaussian noise
  - Poisson noise
- **Noise Amplitude:** Standard deviation maximum 20 px
- **Camera Jitter:** Up to ±20 px/frame
- **Platform Motion:** Up to ±20 px/frame
- **Mandatory Platform Motion:** Linear platform motion mandatory
- **Atmospheric Degradation Modes:**
  - Clear
  - Haze
  - Fog
  - Rain
  - Low Light

---

## 7. Performance Requirements
- **Acquisition Time:** ≤ 2 sec
- **Tracking Error:** ≤ 10 px
- **Target Loss Rate:** < 5%
- **Re-acquisition Time:** ≤ 1 sec
- **Processing Cadence:** ≥ 20 FPS

---

## 8. Benchmark Performance-2 (External Video Feed)
- **Source:** Evaluator-provided MP4 video
- **Video Frame Rate:** 30 FPS
- **Display / Ingestion:** Full-screen video
- **Content:** Noise and moving beacon
- **Pipeline Interface:** MP4 bypasses simulated PTZ camera and enters the same coarse-pointing tracking pipeline directly
- **Verification:** Centroid error must be measurable against reference
