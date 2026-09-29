import * as THREE from 'three';
import { BEACON_LAYER, BEACON_CONFIG, DECOY_CONFIG } from './config.js';
import { createMulberry32 } from './prng.js';

/**
 * Creates and manages optical decoys (fixed stars, decoy satellite, Poisson glints).
 * All decoys render on BEACON_LAYER so they are visible to the gimbal camera feed,
 * sharing the same spectral/chroma characteristics as the real beacon.
 *
 * @param {THREE.Scene} scene
 * @param {Object} [options={}]
 * @returns {Object} Decoys manager interface
 */
export function createDecoys(scene, options = {}) {
  let isEnabled = options.enabled !== undefined ? options.enabled : DECOY_CONFIG.enabled;
  let activeCount = options.count !== undefined ? options.count : DECOY_CONFIG.count;
  let seed = options.seed !== undefined ? options.seed : DECOY_CONFIG.seed;

  let prng = createMulberry32(seed);

  // Group containing all decoy visual meshes
  const decoyGroup = new THREE.Group();
  decoyGroup.name = 'decoyGroup';
  decoyGroup.layers.set(BEACON_LAYER);
  scene.add(decoyGroup);

  // Material identical to the beacon shader
  const baseColor = new THREE.Color(BEACON_CONFIG.color);
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: baseColor },
      uBrightness: { value: BEACON_CONFIG.brightness },
      uCoreRadiusRatio: { value: BEACON_CONFIG.coreRadiusPx / BEACON_CONFIG.haloRadiusPx },
      uSize: { value: BEACON_CONFIG.haloRadiusPx * 2 }
    },
    vertexShader: `
      uniform float uSize;
      void main() {
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mvPosition;
        gl_PointSize = uSize;
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float uBrightness;
      uniform float uCoreRadiusRatio;

      void main() {
        vec2 coord = gl_PointCoord - vec2(0.5);
        float dist = length(coord) * 2.0;
        if (dist > 1.0) discard;

        float haloAlpha = smoothstep(1.0, 0.0, dist);
        float coreAlpha = smoothstep(uCoreRadiusRatio, 0.0, dist);
        vec3 col = mix(uColor, vec3(1.0, 1.0, 1.0), coreAlpha * 0.9);
        float alpha = haloAlpha * uBrightness;

        gl_FragColor = vec4(col * alpha, alpha);
      }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthTest: true,
    depthWrite: false,
    toneMapped: false
  });

  // Decoy definitions
  let decoysList = [];

  function buildDecoys() {
    // Clear old meshes
    while (decoyGroup.children.length > 0) {
      const child = decoyGroup.children[0];
      decoyGroup.remove(child);
      if (child.geometry) child.geometry.dispose();
    }
    decoysList = [];

    prng = createMulberry32(seed);

    // 1. Static Star Point Sources fixed in inertial space
    const starCount = options.starCount ?? DECOY_CONFIG.starCount ?? 2;
    for (let i = 0; i < starCount; i++) {
      const geo = new THREE.BufferGeometry();
      // Positioned on the celestial sphere in directions visible from S-1 orbit
      const theta = prng() * Math.PI * 2;
      const phi = (prng() - 0.5) * Math.PI * 0.6; // within ±54 deg elevation
      const dist = 55 + prng() * 20;

      const x = dist * Math.cos(phi) * Math.cos(theta);
      const y = dist * Math.sin(phi);
      const z = dist * Math.cos(phi) * Math.sin(theta);

      geo.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0], 3));
      const pt = new THREE.Points(geo, material);
      pt.position.set(x, y, z);
      pt.layers.set(BEACON_LAYER);
      decoyGroup.add(pt);

      decoysList.push({
        id: `star_${i + 1}`,
        type: 'star',
        mesh: pt,
        basePos: new THREE.Vector3(x, y, z),
        isSteady: true
      });
    }

    // 2. Steady Decoy Satellite on its own orbit
    const satCount = options.decoySatCount ?? DECOY_CONFIG.decoySatCount ?? 1;
    for (let i = 0; i < satCount; i++) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0], 3));
      const pt = new THREE.Points(geo, material);
      pt.layers.set(BEACON_LAYER);
      decoyGroup.add(pt);

      decoysList.push({
        id: `decoy_sat_${i + 1}`,
        type: 'satellite',
        mesh: pt,
        radius: 23.5,
        speed: 0.24,
        inclination: (45 * Math.PI) / 180,
        phase: prng() * Math.PI * 2,
        isSteady: true
      });
    }

    // 3. Glint flashing randomly (Poisson) near S-2
    const glintCount = options.glintCount ?? DECOY_CONFIG.glintCount ?? 1;
    for (let i = 0; i < glintCount; i++) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0], 3));
      const pt = new THREE.Points(geo, material);
      pt.layers.set(BEACON_LAYER);
      decoyGroup.add(pt);

      decoysList.push({
        id: `glint_${i + 1}`,
        type: 'glint',
        mesh: pt,
        rateHz: DECOY_CONFIG.glintRateHz || 1.5,
        nextFlashTime: 0,
        flashDuration: 0.067, // ~2 feed frames
        isFlashing: false,
        offset: new THREE.Vector3(
          (prng() - 0.5) * 6,
          (prng() - 0.5) * 6,
          (prng() - 0.5) * 6
        ),
        isSteady: false
      });
    }

    syncVisibility();
  }

  function syncVisibility() {
    decoyGroup.visible = isEnabled;
    const countToEnable = isEnabled ? activeCount : 0;
    decoysList.forEach((decoy, index) => {
      const inActiveSubset = index < countToEnable;
      decoy.mesh.visible = inActiveSubset;
    });
  }

  buildDecoys();

  /**
   * Update decoys positions and flashing states with simulation time.
   *
   * @param {number} simTimeSec
   * @param {THREE.Vector3} [targetSatPos] - Optional world position of real target S-2
   */
  function update(simTimeSec, targetSatPos) {
    if (!isEnabled || activeCount <= 0) {
      decoyGroup.visible = false;
      return;
    }
    decoyGroup.visible = true;

    for (let i = 0; i < decoysList.length; i++) {
      const d = decoysList[i];
      if (i >= activeCount) {
        d.mesh.visible = false;
        continue;
      }

      if (d.type === 'star') {
        // Fixed star
        d.mesh.position.copy(d.basePos);
        d.mesh.visible = true;
      } else if (d.type === 'satellite') {
        // Orbital satellite
        const angle = d.phase + d.speed * simTimeSec;
        d.mesh.position.x = Math.cos(angle) * d.radius;
        d.mesh.position.y = Math.sin(angle) * d.radius * Math.sin(d.inclination);
        d.mesh.position.z = Math.sin(angle) * d.radius * Math.cos(d.inclination);
        d.mesh.visible = true;
      } else if (d.type === 'glint') {
        // Poisson flashing glint near S-2
        if (targetSatPos) {
          d.mesh.position.copy(targetSatPos).add(d.offset);
        }

        // Poisson interval: Delta t = -ln(U) / lambda
        if (simTimeSec >= d.nextFlashTime) {
          const u = Math.max(1e-6, prng());
          const interval = -Math.log(u) / Math.max(0.1, d.rateHz);
          d.nextFlashTime = simTimeSec + interval;
          d.isFlashing = true;
        }

        const timeSinceFlashStart = simTimeSec - (d.nextFlashTime - d.flashDuration);
        d.isFlashing = timeSinceFlashStart >= 0 && timeSinceFlashStart < d.flashDuration;
        d.mesh.visible = d.isFlashing;
      }
    }
  }

  function setEnabled(enabled) {
    isEnabled = !!enabled;
    syncVisibility();
  }

  function setCount(count) {
    activeCount = Math.max(0, Math.min(decoysList.length, count));
    syncVisibility();
  }

  function setSeed(newSeed) {
    seed = (newSeed >>> 0) || 42;
    buildDecoys();
  }

  return {
    group: decoyGroup,
    update,
    setEnabled,
    setCount,
    setSeed,
    getDecoys: () => decoysList,
    getCount: () => activeCount,
    isEnabled: () => isEnabled
  };
}
