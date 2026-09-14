import * as THREE from 'three';
import { EARTH_RADIUS } from './loadAssets.js';

// ============================================================
// TWEAKABLE ORBIT CONSTANTS
// ============================================================

export const ORBIT_1_RADIUS      = 20;    // 2× Earth radius
export const ORBIT_1_SPEED       = 0.3;   // radians per second
export const ORBIT_1_INCLINATION = 25;    // degrees

export const ORBIT_2_RADIUS      = 26;    // 2.6× Earth radius
export const ORBIT_2_SPEED       = 0.2;   // radians per second
export const ORBIT_2_INCLINATION = 65;    // degrees

/**
 * Optional rotation offset (radians) applied after lookAt() to fix
 * models whose "front" axis doesn't match Three.js's default +Z.
 * Adjust these if a satellite appears to point sideways after lookAt.
 */
export const SATELLITE_ROTATION_OFFSET = { x: 0, y: 0, z: 0 };

// ---- Orbit line visuals ----
const ORBIT_LINE_COLOR_1   = 0x6699cc;  // steel blue
const ORBIT_LINE_COLOR_2   = 0xcc7766;  // warm salmon
const ORBIT_LINE_OPACITY   = 0.6;
const ORBIT_LINE_SEGMENTS  = 128;

// ---- Internal reusable vector (avoids GC pressure in the hot loop) ----
const _position = new THREE.Vector3();

// ============================================================
// ORBIT LINES
// ============================================================

/**
 * Create a closed ring visualizing an orbit path.
 */
function createOrbitLine(radius, inclinationDeg, color) {
  const points = [];
  const incRad = THREE.MathUtils.degToRad(inclinationDeg);

  for (let i = 0; i <= ORBIT_LINE_SEGMENTS; i++) {
    const theta = (i / ORBIT_LINE_SEGMENTS) * Math.PI * 2;
    const x = Math.cos(theta) * radius;
    const y = Math.sin(theta) * radius * Math.sin(incRad);
    const z = Math.sin(theta) * radius * Math.cos(incRad);
    points.push(new THREE.Vector3(x, y, z));
  }

  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = new THREE.LineBasicMaterial({
    color,
    transparent: true,
    opacity: ORBIT_LINE_OPACITY,
  });

  return new THREE.LineLoop(geometry, material);
}

/**
 * Add both orbit-path rings to the scene.
 */
export function setupOrbitLines(scene) {
  const line1 = createOrbitLine(ORBIT_1_RADIUS, ORBIT_1_INCLINATION, ORBIT_LINE_COLOR_1);
  const line2 = createOrbitLine(ORBIT_2_RADIUS, ORBIT_2_INCLINATION, ORBIT_LINE_COLOR_2);

  scene.add(line1);
  scene.add(line2);

  console.log(`Orbit 1: radius=${ORBIT_1_RADIUS}, inclination=${ORBIT_1_INCLINATION}°`);
  console.log(`Orbit 2: radius=${ORBIT_2_RADIUS}, inclination=${ORBIT_2_INCLINATION}°`);

  return [line1, line2];
}

// ============================================================
// ORBIT STATE
// ============================================================

class OrbitState {
  constructor(radius, speed, inclinationDeg, initialAngleDeg) {
    this.radius      = radius;
    this.speed       = speed;
    this.inclination = THREE.MathUtils.degToRad(inclinationDeg);
    this.angle       = THREE.MathUtils.degToRad(initialAngleDeg);
  }

  update(deltaTime) {
    this.angle += this.speed * deltaTime;
  }

  /**
   * Write the current orbital position into `outVec` (no allocation).
   */
  getPosition(outVec) {
    outVec.x = Math.cos(this.angle) * this.radius;
    outVec.y = Math.sin(this.angle) * this.radius * Math.sin(this.inclination);
    outVec.z = Math.sin(this.angle) * this.radius * Math.cos(this.inclination);
    return outVec;
  }
}

/**
 * Create orbit states for Satellite 1 and Satellite 2.
 */
export function initializeOrbits() {
  return [
    new OrbitState(ORBIT_1_RADIUS, ORBIT_1_SPEED, ORBIT_1_INCLINATION, 0),
    new OrbitState(ORBIT_2_RADIUS, ORBIT_2_SPEED, ORBIT_2_INCLINATION, 180),
  ];
}

// ============================================================
// PER-FRAME UPDATE
// ============================================================

/**
 * Advance orbital angles and move the visible satellite models.
 *
 * `satellites` must be the array `[satellite1, satellite2]` — the actual
 * Three.js groups returned by `loadAssets`, not placeholder objects.
 */
export function updateSatellites(satellites, orbitStates, deltaTime) {
  for (let i = 0; i < satellites.length; i++) {
    const satellite = satellites[i];
    const orbit     = orbitStates[i];

    orbit.update(deltaTime);
    orbit.getPosition(_position);

    satellite.position.copy(_position);

    // Point the satellite toward Earth (at the origin)
    satellite.lookAt(0, 0, 0);

    // Apply optional rotation offset to correct the model's native forward axis
    satellite.rotation.x += SATELLITE_ROTATION_OFFSET.x;
    satellite.rotation.y += SATELLITE_ROTATION_OFFSET.y;
    satellite.rotation.z += SATELLITE_ROTATION_OFFSET.z;
  }
}
