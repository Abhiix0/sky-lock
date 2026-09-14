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

// Manual orbit constants
export const MAX_MANUAL_SATELLITES      = 2;
export const MANUAL_ORBIT_ECCENTRICITY  = 0.25;
export const MIN_SATELLITE_DISTANCE     = EARTH_RADIUS * 1.15; // 11.5
export const MAX_SATELLITE_DISTANCE     = 38.0;

/**
 * Optional rotation offset (radians) applied after lookAt() to fix
 * models whose "front" axis doesn't match Three.js's default +Z.
 */
export const SATELLITE_ROTATION_OFFSET = { x: 0, y: 0, z: 0 };

// ---- Orbit line visuals ----
const ORBIT_LINE_COLOR_1   = 0x6699cc;  // steel blue (automatic 1)
const ORBIT_LINE_COLOR_2   = 0xcc7766;  // warm salmon (automatic 2)
const MANUAL_LINE_COLOR_1  = 0x00e5ff;  // electric cyan (manual 1)
const MANUAL_LINE_COLOR_2  = 0xffaa33;  // vibrant amber (manual 2)
const ORBIT_LINE_OPACITY   = 0.65;
const ORBIT_LINE_SEGMENTS  = 128;

// ---- Internal reusable vectors (avoids GC pressure in hot animation loop) ----
const _position = new THREE.Vector3();
const _tangent = new THREE.Vector3();
const _lookTarget = new THREE.Vector3();

// ============================================================
// AUTOMATIC ORBIT LINES
// ============================================================

/**
 * Create a closed ring visualizing an automatic circular orbit path.
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
 * Add both automatic orbit-path rings to the scene.
 */
export function setupOrbitLines(scene) {
  const line1 = createOrbitLine(ORBIT_1_RADIUS, ORBIT_1_INCLINATION, ORBIT_LINE_COLOR_1);
  const line2 = createOrbitLine(ORBIT_2_RADIUS, ORBIT_2_INCLINATION, ORBIT_LINE_COLOR_2);

  scene.add(line1);
  scene.add(line2);

  return [line1, line2];
}

// ============================================================
// AUTOMATIC ORBIT STATE
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

  getPosition(outVec) {
    outVec.x = Math.cos(this.angle) * this.radius;
    outVec.y = Math.sin(this.angle) * this.radius * Math.sin(this.inclination);
    outVec.z = Math.sin(this.angle) * this.radius * Math.cos(this.inclination);
    return outVec;
  }
}

export function initializeOrbits() {
  return [
    new OrbitState(ORBIT_1_RADIUS, ORBIT_1_SPEED, ORBIT_1_INCLINATION, 0),
    new OrbitState(ORBIT_2_RADIUS, ORBIT_2_SPEED, ORBIT_2_INCLINATION, 180),
  ];
}

export function updateSatellites(satellites, orbitStates, deltaTime) {
  for (let i = 0; i < satellites.length; i++) {
    const satellite = satellites[i];
    const orbit     = orbitStates[i];

    if (!satellite.visible) continue;

    orbit.update(deltaTime);
    orbit.getPosition(_position);

    satellite.position.copy(_position);

    // Orient toward Earth
    satellite.lookAt(0, 0, 0);

    satellite.rotation.x += SATELLITE_ROTATION_OFFSET.x;
    satellite.rotation.y += SATELLITE_ROTATION_OFFSET.y;
    satellite.rotation.z += SATELLITE_ROTATION_OFFSET.z;
  }
}

// ============================================================
// MANUAL ELLIPTICAL ORBIT SYSTEM
// ============================================================

/**
 * Parametric state for a manually created elliptical orbit.
 * Passes directly through the drop position at angle = 0.
 */
export class ManualOrbitState {
  constructor(u, v, a, b, speed) {
    this.u = u;         // Unit vector along major axis (toward drop point)
    this.v = v;         // Unit vector in orbit plane perpendicular to u
    this.a = a;         // Semi-major axis (distance to drop point)
    this.b = b;         // Semi-minor axis (a * sqrt(1 - e^2))
    this.speed = speed; // Angular speed (rad/s)
    this.angle = 0;     // Initial angle is 0, so initial position == drop point!
  }

  update(deltaTime) {
    this.angle += this.speed * deltaTime;
  }

  getPosition(outVec) {
    const cosA = Math.cos(this.angle);
    const sinA = Math.sin(this.angle);
    outVec.set(0, 0, 0)
      .addScaledVector(this.u, this.a * cosA)
      .addScaledVector(this.v, this.b * sinA);
    return outVec;
  }

  getTangent(outVec) {
    // Tangent derivative dPos/dAngle = -u * a * sinA + v * b * cosA
    const cosA = Math.cos(this.angle);
    const sinA = Math.sin(this.angle);
    outVec.set(0, 0, 0)
      .addScaledVector(this.u, -this.a * sinA)
      .addScaledVector(this.v, this.b * cosA)
      .normalize();
    return outVec;
  }
}

/**
 * Generate a visual LineLoop for a manual elliptical orbit.
 */
function createManualOrbitLine(u, v, a, b, color) {
  const points = [];
  for (let i = 0; i <= ORBIT_LINE_SEGMENTS; i++) {
    const theta = (i / ORBIT_LINE_SEGMENTS) * Math.PI * 2;
    const p = new THREE.Vector3()
      .addScaledVector(u, a * Math.cos(theta))
      .addScaledVector(v, b * Math.sin(theta));
    points.push(p);
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
 * Create a new manual elliptical orbit from a user drop position.
 * Returns { orbitState, orbitLine, initialPosition }.
 */
export function createManualOrbit(dropPosition, satelliteIndex) {
  const P = dropPosition.clone();
  let r = P.length();

  // Clamp radius to safe bounds outside Earth
  if (r < MIN_SATELLITE_DISTANCE) {
    P.normalize().multiplyScalar(MIN_SATELLITE_DISTANCE);
    r = MIN_SATELLITE_DISTANCE;
  } else if (r > MAX_SATELLITE_DISTANCE) {
    P.normalize().multiplyScalar(MAX_SATELLITE_DISTANCE);
    r = MAX_SATELLITE_DISTANCE;
  }

  // Major axis unit vector (toward P)
  const u = P.clone().normalize();

  // Pick an inclination reference axis to determine the orbital plane
  // Different reference vectors for satellite 1 and 2 ensure distinct orbital planes
  let refAxis = satelliteIndex === 0
    ? new THREE.Vector3(0.2, 0.95, 0.2).normalize()
    : new THREE.Vector3(-0.35, 0.85, -0.4).normalize();

  // Fallback if reference axis is nearly parallel to u
  if (Math.abs(u.dot(refAxis)) > 0.85) {
    refAxis = new THREE.Vector3(0.9, 0.1, 0.3).normalize();
  }

  // Orbital plane normal vector N
  const N = P.clone().cross(refAxis).normalize();

  // Minor axis unit vector v in the plane
  const v = N.clone().cross(u).normalize();

  // Ellipse dimensions
  const a = r;
  const b = a * Math.sqrt(1 - MANUAL_ORBIT_ECCENTRICITY * MANUAL_ORBIT_ECCENTRICITY);

  // Speed inversely proportional to sqrt(a)
  const speed = 0.28 * Math.sqrt(20 / a);

  const color = satelliteIndex === 0 ? MANUAL_LINE_COLOR_1 : MANUAL_LINE_COLOR_2;
  const orbitLine = createManualOrbitLine(u, v, a, b, color);
  const orbitState = new ManualOrbitState(u, v, a, b, speed);

  return {
    orbitState,
    orbitLine,
    initialPosition: P
  };
}

/**
 * Update all active manual satellites along their elliptical orbits.
 */
export function updateManualSatellites(satellites, orbitStates, deltaTime) {
  for (let i = 0; i < satellites.length; i++) {
    const satellite = satellites[i];
    const orbit = orbitStates[i];

    if (!satellite || !orbit || !satellite.visible) continue;

    orbit.update(deltaTime);
    orbit.getPosition(_position);

    satellite.position.copy(_position);

    // Orient along direction of travel
    orbit.getTangent(_tangent);
    _lookTarget.copy(satellite.position).add(_tangent);
    satellite.lookAt(_lookTarget);

    satellite.rotation.x += SATELLITE_ROTATION_OFFSET.x;
    satellite.rotation.y += SATELLITE_ROTATION_OFFSET.y;
    satellite.rotation.z += SATELLITE_ROTATION_OFFSET.z;
  }
}
