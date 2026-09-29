import * as THREE from 'three';
import { BEACON_CONFIG, BEACON_CODE, BEACON_LAYER } from './config.js';
import { disturbances } from './disturbances.js';

/**
 * Reusable vectors to avoid allocations per frame.
 */
const _targetPos = new THREE.Vector3();
const _obsPos = new THREE.Vector3();
const _dirToObs = new THREE.Vector3();

/**
 * Creates the optical beacon on the target satellite (S-2).
 *
 * @param {THREE.Scene} scene - The main Three.js scene
 * @param {THREE.WebGLRenderer} [renderer] - Optional renderer for checking WebGL limits
 * @returns {Object} Beacon interface
 */
export function createBeacon(scene, renderer) {
  let isEnabled = BEACON_CONFIG.enabled;
  let brightness = BEACON_CONFIG.brightness;
  let blinkHz = BEACON_CONFIG.blinkHz;
  let blinkDuty = BEACON_CONFIG.blinkDuty;

  // Blink code support (Phase 3B)
  let beaconMode = BEACON_CODE.mode || 'steady'; // 'steady' | 'code'
  let codeBits = BEACON_CODE.bits || '10110010';
  let bitPeriodSec = BEACON_CODE.bitPeriodSec || 0.1;

  const baseColor = new THREE.Color(BEACON_CONFIG.color);

  // Check point size range if renderer context is available
  let maxPointSize = 100;
  if (renderer) {
    const gl = renderer.getContext();
    if (gl) {
      const range = gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE);
      if (range && range[1]) {
        maxPointSize = range[1];
      }
    }
  }

  const requestedSize = BEACON_CONFIG.haloRadiusPx * 2;
  const pointSize = Math.min(requestedSize, maxPointSize);
  if (requestedSize > maxPointSize) {
    console.warn(`[Beacon] Requested point size ${requestedSize}px exceeds WebGL max ${maxPointSize}px.`);
  }

  // Single point geometry
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0], 3));

  // Custom shader material for a soft-edged point with a bright core
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: baseColor },
      uBrightness: { value: brightness },
      uCoreRadiusRatio: { value: BEACON_CONFIG.coreRadiusPx / BEACON_CONFIG.haloRadiusPx },
      uSize: { value: pointSize },
      uPixelOffset: { value: new THREE.Vector2(0, 0) },
      uViewportSize: { value: new THREE.Vector2(640, 480) },
      uScintillation: { value: 1.0 }
    },
    vertexShader: `
      uniform float uSize;
      uniform vec2 uPixelOffset;
      uniform vec2 uViewportSize;

      void main() {
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mvPosition;
        // Apply turbulence pixel wander before perspective divide
        gl_Position.xy += (uPixelOffset * (2.0 / uViewportSize)) * gl_Position.w;
        gl_PointSize = uSize;
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float uBrightness;
      uniform float uCoreRadiusRatio;
      uniform float uScintillation;

      void main() {
        vec2 coord = gl_PointCoord - vec2(0.5);
        float dist = length(coord) * 2.0; // 0.0 at center, 1.0 at boundary
        if (dist > 1.0) discard;

        // Smooth halo falloff
        float haloAlpha = smoothstep(1.0, 0.0, dist);

        // Core intensity
        float coreAlpha = smoothstep(uCoreRadiusRatio, 0.0, dist);

        // Blend magenta halo with bright near-white core
        vec3 col = mix(uColor, vec3(1.0, 1.0, 1.0), coreAlpha * 0.9);
        float alpha = haloAlpha * uBrightness * uScintillation;

        gl_FragColor = vec4(col * alpha, alpha);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthTest: true,
    depthWrite: false,
    toneMapped: false
  });

  const pointMesh = new THREE.Points(geometry, material);
  pointMesh.name = 'targetBeacon';
  pointMesh.renderOrder = 999;
  pointMesh.layers.set(BEACON_LAYER);
  scene.add(pointMesh);

  // Optional marker for main camera view (layer 0)
  let markerMesh = null;
  if (BEACON_CONFIG.showMarkerInMainView) {
    const ringGeo = new THREE.RingGeometry(0.3, 0.45, 32);
    const ringMat = new THREE.MeshBasicMaterial({
      color: BEACON_CONFIG.color,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.8,
      depthTest: true
    });
    markerMesh = new THREE.Mesh(ringGeo, ringMat);
    markerMesh.layers.set(0); // Only seen by main camera
    scene.add(markerMesh);
  }

  /**
   * Update beacon position and blink state.
   *
   * @param {Object} targetSat - Target satellite object with .model
   * @param {number} simTimeSec - Current simulation time in seconds
   * @param {Object} [observerSat] - Optional observer satellite for offset
   */
  function update(targetSat, simTimeSec, observerSat) {
    if (!targetSat || !targetSat.model || targetSat.model.visible === false || !isEnabled) {
      pointMesh.visible = false;
      if (markerMesh) markerMesh.visible = false;
      return;
    }

    // Evaluate blink state
    let isBlinkOn = true;
    if (beaconMode === 'code' && codeBits.length > 0) {
      const codeLen = codeBits.length;
      const cycleTime = codeLen * bitPeriodSec;
      const tMod = ((simTimeSec % cycleTime) + cycleTime) % cycleTime;
      const bitIdx = Math.floor(tMod / bitPeriodSec) % codeLen;
      isBlinkOn = codeBits[bitIdx] === '1';
    } else if (blinkHz > 0) {
      const phase = ((simTimeSec * blinkHz) % 1 + 1) % 1;
      isBlinkOn = phase < blinkDuty;
    }

    pointMesh.visible = isEnabled && isBlinkOn;
    if (markerMesh) markerMesh.visible = pointMesh.visible;

    if (!pointMesh.visible) return;

    // Synchronize position in world space
    targetSat.model.getWorldPosition(_targetPos);

    if (!BEACON_CONFIG.hideTargetBodyInFeed && observerSat && observerSat.model) {
      observerSat.model.getWorldPosition(_obsPos);
      _dirToObs.subVectors(_obsPos, _targetPos).normalize();
      _targetPos.addScaledVector(_dirToObs, 2.5);
    }

    // Update atmospheric turbulence perturbations (image wander + scintillation)
    const turb = disturbances.getTurbulence(simTimeSec);
    material.uniforms.uPixelOffset.value.set(turb.wanderPx[0], turb.wanderPx[1]);
    material.uniforms.uScintillation.value = turb.scintillation;

    pointMesh.position.copy(_targetPos);
    if (markerMesh) {
      markerMesh.position.copy(_targetPos);
      if (observerSat && observerSat.model) {
        markerMesh.lookAt(_obsPos);
      }
    }
  }

  /**
   * Directly set perturbation uniforms.
   *
   * @param {number} offsetX - X offset in pixels
   * @param {number} offsetY - Y offset in pixels
   * @param {number} scintillation - Multiplicative intensity factor
   */
  function setPerturbations(offsetX, offsetY, scintillation = 1.0) {
    material.uniforms.uPixelOffset.value.set(offsetX, offsetY);
    material.uniforms.uScintillation.value = scintillation;
  }

  /**
   * Enable or disable beacon.
   * @param {boolean} enabled
   */
  function setEnabled(enabled) {
    isEnabled = !!enabled;
    pointMesh.visible = isEnabled;
    if (markerMesh) markerMesh.visible = isEnabled;
  }

  /**
   * Set beacon brightness multiplier.
   * @param {number} val
   */
  function setBrightness(val) {
    brightness = val;
    material.uniforms.uBrightness.value = val;
  }

  /**
   * Configure blink parameters.
   * @param {number} hz - Frequency in Hz
   * @param {number} [duty=0.5] - Duty cycle [0, 1]
   */
  function setBlink(hz, duty = 0.5) {
    blinkHz = hz;
    blinkDuty = duty;
  }

  /**
   * Set repeating bit code pattern and bit period.
   * @param {string} bits - Binary string (e.g. '10110010')
   * @param {number} [period=0.1] - Bit duration in seconds
   */
  function setCode(bits, period = 0.1) {
    codeBits = bits;
    bitPeriodSec = period;
  }

  /**
   * Set beacon modulation mode ('steady' | 'code').
   * @param {'steady'|'code'} newMode
   */
  function setMode(newMode) {
    beaconMode = newMode;
  }

  return {
    object: pointMesh,
    markerObject: markerMesh,
    update,
    setEnabled,
    setBrightness,
    setBlink,
    setPerturbations,
    setCode,
    setMode,
    getMode: () => beaconMode
  };
}

