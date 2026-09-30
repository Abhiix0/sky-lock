/**
 * Runtime observer/target identity state.
 *
 * Decouples the mutable runtime selection of which satellite hosts the gimbal
 * camera (observer) from the compile-time CAMERA_CONFIG constants.
 * All code that previously read CAMERA_CONFIG.observerId / targetId should
 * read from this module instead so that the UI selector takes effect immediately.
 */

import { CAMERA_CONFIG } from './config.js';

// ---- Mutable runtime state ----
let _observerId = CAMERA_CONFIG.observerId ?? 'S-1';
let _targetId = CAMERA_CONFIG.targetId ?? 'S-2';

/** @returns {string} */
export function getObserverId() {
  return _observerId;
}

/** @returns {string} */
export function getTargetId() {
  return _targetId;
}

/**
 * Switch the observer to `newObserverId`.
 * Automatically sets the target to the other satellite ID.
 * Returns false if newObserverId equals the current observer (no-op).
 *
 * @param {string} newObserverId
 * @param {string[]} [allIds=['S-1','S-2']] - Known satellite IDs
 * @returns {boolean} True if the observer actually changed
 */
export function setObserver(newObserverId, allIds = ['S-1', 'S-2']) {
  if (newObserverId === _observerId) return false;
  _observerId = newObserverId;
  // Target is the first active ID that isn't the new observer
  _targetId = allIds.find((id) => id !== newObserverId) ?? allIds[0];
  return true;
}
