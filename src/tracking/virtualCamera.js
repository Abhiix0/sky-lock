import * as THREE from 'three';
import { CAMERA_CONFIG, BEACON_CONFIG, BEACON_LAYER } from './config.js';
import { getLinkRoot } from './linkLine.js';

/**
 * Virtual gimbal camera mounted on the observer satellite.
 *
 * Architecture:
 *   rigRoot (Group, unscaled, in world space)
 *     └─ panGroup (Group, rotates about local Y = body-up)
 *          └─ tiltGroup (Group, rotates about local X = body-right)
 *               └─ PerspectiveCamera (offset along +Z so it sits outside the mesh)
 *
 * The rig root is NOT parented to the satellite model — the satellite model is
 * scaled/normalized and a scaled camera parent distorts the projection. Instead,
 * every frame we copy the observer's world position and quaternion into the
 * unscaled rigRoot.
 */

// ============================================================
// CONFIGURATION
// ============================================================

const {
  fovDeg,
  width,
  height,
  near,
  far,
  feedRateHz,
  panLimitDeg,
  tiltLimitDeg
} = CAMERA_CONFIG;

/** Offset the camera slightly outward so it never sits inside the satellite mesh. */
const CAMERA_OFFSET_Z = 2.5;

// ============================================================
// INTERNAL REUSABLE OBJECTS
// ============================================================

const _worldPos = new THREE.Vector3();
const _worldQuat = new THREE.Quaternion();
const _targetWorld = new THREE.Vector3();
const _localTarget = new THREE.Vector3();
const _projected = new THREE.Vector3();

// ============================================================
// PUBLIC API
// ============================================================

/**
 * Create the virtual gimbal camera system.
 *
 * @param {THREE.Scene} scene
 * @param {THREE.WebGLRenderer} renderer
 * @returns {Object} virtualCamera API
 */
export function createVirtualCamera(scene, renderer) {
  // ---- Gimbal rig (unscaled, lives in world space) ----
  const rigRoot = new THREE.Group();
  rigRoot.name = 'virtualCameraRig';

  const panGroup = new THREE.Group();
  panGroup.name = 'panGroup';
  rigRoot.add(panGroup);

  const tiltGroup = new THREE.Group();
  tiltGroup.name = 'tiltGroup';
  panGroup.add(tiltGroup);

  // ---- PerspectiveCamera ----
  const cam = new THREE.PerspectiveCamera(fovDeg, width / height, near, far);
  cam.position.set(0, 0, -CAMERA_OFFSET_Z);
  cam.layers.enable(BEACON_LAYER);
  tiltGroup.add(cam);

  scene.add(rigRoot);

  // ---- Offscreen render target ----
  const renderTarget = new THREE.WebGLRenderTarget(width, height, {
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
    format: THREE.RGBAFormat,
    type: THREE.UnsignedByteType,
    colorSpace: THREE.SRGBColorSpace
  });

  // ---- Reusable pixel buffer (no per-frame allocations) ----
  const pixelBuffer = new Uint8Array(width * height * 4);

  // ---- State ----
  let panDeg = 90; // Default aimed at Earth (+X in body frame)
  let tiltDeg = 0;
  let frameId = 0;
  let lastFeedTime = 0;
  const feedIntervalMs = 1000 / feedRateHz;

  /** Latest frame payload (mutated in place). */
  const frame = {
    width,
    height,
    data: pixelBuffer,
    timestamp: 0,
    frameId: 0
  };

  // ---- Helpers ----

  /**
   * Clamp and apply pan/tilt angles.
   *
   * @param {number} pan  - Desired pan in degrees
   * @param {number} tilt - Desired tilt in degrees
   */
  function setPanTilt(pan, tilt) {
    panDeg = THREE.MathUtils.clamp(pan, -panLimitDeg, panLimitDeg);
    tiltDeg = THREE.MathUtils.clamp(tilt, -tiltLimitDeg, tiltLimitDeg);
    panGroup.rotation.y = THREE.MathUtils.degToRad(-panDeg);
    tiltGroup.rotation.x = THREE.MathUtils.degToRad(tiltDeg);
  }

  // Initialize gimbal at Earth
  setPanTilt(panDeg, tiltDeg);

  /**
   * @returns {{ panDeg: number, tiltDeg: number }}
   */
  function getPanTilt() {
    return { panDeg, tiltDeg };
  }

  /**
   * @returns {{ width: number, height: number, data: Uint8Array, timestamp: number, frameId: number }}
   */
  function getFrame() {
    return frame;
  }

  /**
   * Collect scene objects that must be hidden during the feed render.
   * Returns an array of { object, wasVisible } entries.
   *
   * @param {THREE.Object3D} observerModel
   * @param {THREE.Object3D} [targetModel]
   * @returns {Array<{ object: THREE.Object3D, wasVisible: boolean }>}
   */
  function collectHiddenObjects(observerModel, targetModel) {
    const hidden = [];

    // 1. Observer's own model
    if (observerModel) {
      hidden.push({ object: observerModel, wasVisible: observerModel.visible });
    }

    // Target satellite model if configured (beacon as point source)
    if (BEACON_CONFIG.hideTargetBodyInFeed && targetModel) {
      hidden.push({ object: targetModel, wasVisible: targetModel.visible });
    }

    // 2. ISL link beam group
    const linkRoot = getLinkRoot();
    if (linkRoot) {
      hidden.push({ object: linkRoot, wasVisible: linkRoot.visible });
    }

    // 3. Orbit lines (LineLoop / Line objects at the scene root)
    scene.children.forEach((child) => {
      if (child.isLineLoop || (child.isLine && child !== linkRoot)) {
        hidden.push({ object: child, wasVisible: child.visible });
      }
    });

    return hidden;
  }

  /**
   * Update the rig to track the observer satellite, render the feed at feedRateHz.
   *
   * @param {Object} observerSat - Satellite data object with .model property
   * @param {Object} [targetSat] - Optional target satellite data object with .model property
   */
  function update(observerSat, targetSat) {
    if (!observerSat || !observerSat.model) return;

    // Copy world position and quaternion into the unscaled rig root
    observerSat.model.getWorldPosition(_worldPos);
    observerSat.model.getWorldQuaternion(_worldQuat);
    rigRoot.position.copy(_worldPos);
    rigRoot.quaternion.copy(_worldQuat);

    // Rate-limit feed rendering
    const now = performance.now();
    if (now - lastFeedTime < feedIntervalMs) return;
    lastFeedTime = now;

    // ---- Temporarily hide objects that a real camera wouldn't see ----
    const hiddenEntries = collectHiddenObjects(observerSat.model, targetSat ? targetSat.model : null);
    hiddenEntries.forEach((entry) => {
      entry.object.visible = false;
    });

    // ---- Save renderer state ----
    const savedToneMapping = renderer.toneMapping;
    const savedExposure = renderer.toneMappingExposure;
    const savedOutputColorSpace = renderer.outputColorSpace;

    // Apply the same tone mapping the main view uses so the feed looks similar
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    // ---- Render to offscreen target ----
    renderer.setRenderTarget(renderTarget);
    renderer.render(scene, cam);

    // ---- Read pixels into reusable buffer ----
    renderer.readRenderTargetPixels(renderTarget, 0, 0, width, height, pixelBuffer);

    // ---- Restore renderer state ----
    renderer.setRenderTarget(null);
    renderer.toneMapping = savedToneMapping;
    renderer.toneMappingExposure = savedExposure;
    renderer.outputColorSpace = savedOutputColorSpace;

    // ---- Restore hidden objects ----
    hiddenEntries.forEach((entry) => {
      entry.object.visible = entry.wasVisible;
    });

    // ---- Update frame payload ----
    frameId++;
    frame.timestamp = now;
    frame.frameId = frameId;
  }

  /**
   * Compute the ground-truth direction from the camera to the target satellite.
   * Returns the true pan/tilt angles and the pixel position of the target in the
   * camera image.
   *
   * @param {Object} targetSat - Satellite data object with .model property
   * @returns {{ panDeg: number, tiltDeg: number, pixelX: number, pixelY: number, inFrustum: boolean }}
   */
  function getGroundTruthDirection(targetSat) {
    if (!targetSat || !targetSat.model) {
      return { panDeg: 0, tiltDeg: 0, pixelX: 0, pixelY: 0, inFrustum: false };
    }

    // Get target world position
    targetSat.model.getWorldPosition(_targetWorld);

    // Transform target into the rig root's local space (body frame)
    // to compute the ideal pan/tilt from the satellite body frame origin.
    rigRoot.updateMatrixWorld(true);
    _localTarget.copy(_targetWorld);
    rigRoot.worldToLocal(_localTarget);

    // Pan = atan2(x, -z), Tilt = atan2(y, sqrt(x^2 + z^2))
    const gtPanDeg = THREE.MathUtils.radToDeg(Math.atan2(_localTarget.x, -_localTarget.z));
    const horizDist = Math.sqrt(_localTarget.x * _localTarget.x + _localTarget.z * _localTarget.z);
    const gtTiltDeg = THREE.MathUtils.radToDeg(Math.atan2(_localTarget.y, horizDist));

    // Project target world position into the camera's image plane
    cam.updateMatrixWorld(true);
    _projected.copy(_targetWorld).project(cam);

    const pixelX = ((_projected.x + 1) / 2) * width;
    const pixelY = ((1 - _projected.y) / 2) * height;
    const inFrustum =
      _projected.z > 0 &&
      _projected.z < 1 &&
      pixelX >= 0 &&
      pixelX < width &&
      pixelY >= 0 &&
      pixelY < height;

    return {
      panDeg: gtPanDeg,
      tiltDeg: gtTiltDeg,
      pixelX,
      pixelY,
      inFrustum
    };
  }

  return {
    camera: cam,
    rigRoot,
    setPanTilt,
    getPanTilt,
    getFrame,
    update,
    getGroundTruthDirection
  };
}
