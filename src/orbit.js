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

// Manual orbit constraints
export const MAX_MANUAL_SATELLITES      = 2;
export const MANUAL_ORBIT_ECCENTRICITY  = 0.25;
export const MIN_SATELLITE_DISTANCE     = EARTH_RADIUS * 1.15; // 11.5
export const MAX_SATELLITE_DISTANCE     = 38.0;

/**
 * Optional rotation offset applied to align native GLB forward axis.
 */
export const SATELLITE_ROTATION_OFFSET = { x: 0, y: 0, z: 0 };
const _offsetQuat = new THREE.Quaternion().setFromEuler(
  new THREE.Euler(SATELLITE_ROTATION_OFFSET.x, SATELLITE_ROTATION_OFFSET.y, SATELLITE_ROTATION_OFFSET.z)
);

// ---- Orbit line visuals ----
const ORBIT_LINE_COLOR_1   = 0x6699cc;  // steel blue (automatic 1)
const ORBIT_LINE_COLOR_2   = 0xcc7766;  // warm salmon (automatic 2)
const MANUAL_LINE_COLOR_1  = 0x00e5ff;  // electric cyan (manual 1)
const MANUAL_LINE_COLOR_2  = 0xffaa33;  // vibrant amber (manual 2)
const ORBIT_LINE_OPACITY   = 0.65;
const ORBIT_LINE_SEGMENTS  = 128;

// ---- Internal reusable math objects (prevents GC pressure in animation loop) ----
const _position = new THREE.Vector3();
const _tangent = new THREE.Vector3();
const _right = new THREE.Vector3();
const _up = new THREE.Vector3();
const _forward = new THREE.Vector3();
const _basisMatrix = new THREE.Matrix4();
const _targetQuat = new THREE.Quaternion();

// ============================================================
// AUTOMATIC ORBIT LINES
// ============================================================

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

export class OrbitState {
  constructor(radius, speed, inclinationDeg, initialAngleDeg) {
    this.radius      = radius;
    this.speed       = speed;
    this.inclination = THREE.MathUtils.degToRad(inclinationDeg);
    this.angle       = THREE.MathUtils.degToRad(initialAngleDeg);

    // Constant orbital plane normal vector N = (0, -cos(inc), sin(inc))
    this.normal = new THREE.Vector3(
      0,
      -Math.cos(this.inclination),
      Math.sin(this.inclination)
    ).normalize();
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

  getTangent(outVec) {
    // Velocity direction dPos/dAngle = (-r*sin(A), r*cos(A)*sin(inc), r*cos(A)*cos(inc))
    outVec.x = -Math.sin(this.angle);
    outVec.y = Math.cos(this.angle) * Math.sin(this.inclination);
    outVec.z = Math.cos(this.angle) * Math.cos(this.inclination);
    return outVec.normalize();
  }

  /**
   * Calculates a rock-solid, flip-free target orientation quaternion
   * where Forward is direction of travel, and Up is the constant orbit normal.
   */
  getOrientation(outQuat) {
    this.getTangent(_forward);
    _up.copy(this.normal);
    // Right = Up x Forward (Ensures right-handed coordinate system: X x Y = Z)
    _right.crossVectors(_up, _forward).normalize();
    _up.crossVectors(_forward, _right).normalize();

    // Reconstruct exact orthonormal basis (det = +1)
    _basisMatrix.makeBasis(_right, _up, _forward);
    outQuat.setFromRotationMatrix(_basisMatrix);
    outQuat.multiply(_offsetQuat);
    return outQuat;
  }
}

export function initializeOrbits() {
  return [
    new OrbitState(ORBIT_1_RADIUS, ORBIT_1_SPEED, ORBIT_1_INCLINATION, 0),
    new OrbitState(ORBIT_2_RADIUS, ORBIT_2_SPEED, ORBIT_2_INCLINATION, 180),
  ];
}

// ============================================================
// MANUAL ELLIPTICAL ORBIT STATE
// ============================================================

export class ManualOrbitState {
  constructor(u, v, a, b, speed, normal) {
    this.u = u;         // Major axis unit vector (toward drop position)
    this.v = v;         // Minor axis unit vector in orbit plane
    this.a = a;         // Semi-major axis
    this.b = b;         // Semi-minor axis
    this.speed = speed; // Angular velocity (rad/s)
    this.angle = 0;     // Initial angle is 0 => pos(0) == drop position!
    this.normal = normal; // Constant orbit plane normal
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

  /**
   * Calculates flip-free target orientation quaternion along direction of travel.
   */
  getOrientation(outQuat) {
    this.getTangent(_forward);
    _up.copy(this.normal);
    // Right = Up x Forward (Ensures right-handed coordinate system: X x Y = Z)
    _right.crossVectors(_up, _forward).normalize();
    _up.crossVectors(_forward, _right).normalize();

    _basisMatrix.makeBasis(_right, _up, _forward);
    outQuat.setFromRotationMatrix(_basisMatrix);
    outQuat.multiply(_offsetQuat);
    return outQuat;
  }
}

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

  // Reference axis to determine the orbital plane
  let refAxis = satelliteIndex === 0
    ? new THREE.Vector3(0.2, 0.95, 0.2).normalize()
    : new THREE.Vector3(-0.35, 0.85, -0.4).normalize();

  if (Math.abs(u.dot(refAxis)) > 0.85) {
    refAxis = new THREE.Vector3(0.9, 0.1, 0.3).normalize();
  }

  // Constant orbital plane normal N
  const N = P.clone().cross(refAxis).normalize();

  // Minor axis unit vector v in the plane
  const v = N.clone().cross(u).normalize();

  // Ellipse axes
  const a = r;
  const b = a * Math.sqrt(1 - MANUAL_ORBIT_ECCENTRICITY * MANUAL_ORBIT_ECCENTRICITY);

  const speed = 0.28 * Math.sqrt(20 / a);

  const color = satelliteIndex === 0 ? MANUAL_LINE_COLOR_1 : MANUAL_LINE_COLOR_2;
  const orbitLine = createManualOrbitLine(u, v, a, b, color);
  const orbitState = new ManualOrbitState(u, v, a, b, speed, N);

  return {
    orbitState,
    orbitLine,
    initialPosition: P
  };
}
