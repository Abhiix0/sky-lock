import { CAMERA_CONFIG } from './config.js';

/**
 * Wraps angle to (-180, 180] degrees.
 *
 * @param {number} deg
 * @returns {number}
 */
export function wrapDeg(deg) {
  let a = (deg + 180) % 360;
  if (a <= 0) a += 360;
  return a - 180;
}

/**
 * Shortest signed angular difference from current to target in (-180, 180] degrees.
 *
 * @param {number} targetDeg
 * @param {number} currentDeg
 * @returns {number}
 */
export function angularDiffDeg(targetDeg, currentDeg) {
  return wrapDeg(targetDeg - currentDeg);
}

/**
 * Convert pixel coordinates on the camera sensor into body-frame pan/tilt line-of-sight angles.
 *
 * Gimbal kinematics:
 * 1. Pan rotates about local body Y by -pan.
 * 2. Tilt rotates about local gimbal X by +tilt.
 * 3. Camera optical axis points down -Z; +X is right, +Y is up.
 * 4. Image pixel origin (0, 0) is top-left.
 *
 * @param {number} px - Pixel X coordinate [0, width)
 * @param {number} py - Pixel Y coordinate [0, height)
 * @param {number} panDeg - Current gimbal pan angle in degrees
 * @param {number} tiltDeg - Current gimbal tilt angle in degrees
 * @param {Object} [cameraCfg=CAMERA_CONFIG] - Camera parameters
 * @returns {{ panDeg: number, tiltDeg: number }}
 */
export function pixelToBodyAngles(px, py, panDeg, tiltDeg, cameraCfg = CAMERA_CONFIG) {
  const { width, height, fovDeg } = cameraCfg;

  const fovRad = (fovDeg * Math.PI) / 180;
  const focalLength = height / 2 / Math.tan(fovRad / 2);

  const cx = width / 2;
  const cy = height / 2;

  // Normalized ray in camera space (origin top-left -> py down, so camY is inverted)
  const camX = (px - cx) / focalLength;
  const camY = -(py - cy) / focalLength;
  const camZ = -1.0;

  const norm = Math.hypot(camX, camY, camZ);
  const nx = camX / norm;
  const ny = camY / norm;
  const nz = camZ / norm;

  // Rotate by tilt about X (+tilt)
  const tiltRad = (tiltDeg * Math.PI) / 180;
  const cosT = Math.cos(tiltRad);
  const sinT = Math.sin(tiltRad);

  const xPan = nx;
  const yPan = ny * cosT - nz * sinT;
  const zPan = ny * sinT + nz * cosT;

  // Rotate by pan about Y (-pan)
  const panRad = (panDeg * Math.PI) / 180;
  const cosP = Math.cos(panRad);
  const sinP = Math.sin(panRad);

  // Rotation about Y by theta = -panRad:
  // xBody = xPan * cos(-p) + zPan * sin(-p) = xPan * cosP - zPan * sinP
  // zBody = -xPan * sin(-p) + zPan * cos(-p) = xPan * sinP + zPan * cosP
  const xBody = xPan * cosP - zPan * sinP;
  const yBody = yPan;
  const zBody = xPan * sinP + zPan * cosP;

  // Conventions from Preamble:
  // pan = atan2(x, -z), tilt = atan2(y, hypot(x, z))
  const bodyPanRad = Math.atan2(xBody, -zBody);
  const bodyTiltRad = Math.atan2(yBody, Math.hypot(xBody, zBody));

  return {
    panDeg: wrapDeg((bodyPanRad * 180) / Math.PI),
    tiltDeg: (bodyTiltRad * 180) / Math.PI
  };
}

/**
 * Convert body-frame pan/tilt line-of-sight angles into pixel coordinates on the camera sensor.
 *
 * @param {number} targetPanDeg - Target line-of-sight pan in degrees
 * @param {number} targetTiltDeg - Target line-of-sight tilt in degrees
 * @param {number} gimbalPanDeg - Current gimbal pan angle in degrees
 * @param {number} gimbalTiltDeg - Current gimbal tilt angle in degrees
 * @param {Object} [cameraCfg=CAMERA_CONFIG] - Camera parameters
 * @returns {{ px: number, py: number, inFrustum: boolean, visibleInFront: boolean }}
 */
export function bodyAnglesToPixel(
  targetPanDeg,
  targetTiltDeg,
  gimbalPanDeg,
  gimbalTiltDeg,
  cameraCfg = CAMERA_CONFIG
) {
  const { width, height, fovDeg } = cameraCfg;

  const fovRad = (fovDeg * Math.PI) / 180;
  const focalLength = height / 2 / Math.tan(fovRad / 2);

  const cx = width / 2;
  const cy = height / 2;

  // Direction vector in body frame from target angles
  const tPanRad = (targetPanDeg * Math.PI) / 180;
  const tTiltRad = (targetTiltDeg * Math.PI) / 180;

  const cosTP = Math.cos(tPanRad);
  const sinTP = Math.sin(tPanRad);
  const cosTT = Math.cos(tTiltRad);
  const sinTT = Math.sin(tTiltRad);

  const xBody = sinTP * cosTT;
  const yBody = sinTT;
  const zBody = -cosTP * cosTT;

  // Inverse pan rotation (rotate by +pan about Y)
  const gPanRad = (gimbalPanDeg * Math.PI) / 180;
  const cosGP = Math.cos(gPanRad);
  const sinGP = Math.sin(gPanRad);

  const xPan = xBody * cosGP + zBody * sinGP;
  const yPan = yBody;
  const zPan = -xBody * sinGP + zBody * cosGP;

  // Inverse tilt rotation (rotate by -tilt about X)
  const gTiltRad = (gimbalTiltDeg * Math.PI) / 180;
  const cosGT = Math.cos(gTiltRad);
  const sinGT = Math.sin(gTiltRad);

  const xCam = xPan;
  const yCam = yPan * cosGT + zPan * sinGT;
  const zCam = -yPan * sinGT + zPan * cosGT;

  const visibleInFront = zCam < -1e-6;

  // Project onto pinhole camera image plane
  const px = cx + (xCam / -zCam) * focalLength;
  const py = cy - (yCam / -zCam) * focalLength;

  const inFrustum = visibleInFront && px >= 0 && px < width && py >= 0 && py < height;

  return {
    px,
    py,
    inFrustum,
    visibleInFront
  };
}
