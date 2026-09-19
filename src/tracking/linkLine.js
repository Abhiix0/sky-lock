import * as THREE from 'three';

/**
 * Inter-Satellite Link Line (ISL)
 * Draws and updates a pulsating cyan link line between active satellites.
 */

let linkLine = null;
let lineGeometry = null;
let lineMaterial = null;

const _posA = new THREE.Vector3();
const _posB = new THREE.Vector3();

/**
 * Update the inter-satellite link line each frame.
 * Renders between active (non-paused, visible) satellites.
 *
 * @param {THREE.Scene} scene
 * @param {Array<Object>} activeSatellites
 */
export function update(scene, activeSatellites) {
  if (!scene) return;

  // Filter only active, operational satellites (visible and not paused)
  const active = (activeSatellites || []).filter(
    (sat) => sat && sat.model && !sat.paused && sat.model.visible !== false
  );

  // When fewer than 2 active satellites exist, hide the link
  if (active.length < 2) {
    if (linkLine) {
      linkLine.visible = false;
    }
    return;
  }

  // Get current world positions of the primary active satellite pair
  active[0].model.getWorldPosition(_posA);
  active[1].model.getWorldPosition(_posB);

  // Lazy-initialize the THREE.Line
  if (!linkLine) {
    lineGeometry = new THREE.BufferGeometry().setFromPoints([_posA, _posB]);
    lineMaterial = new THREE.LineBasicMaterial({
      color: 0x00f3ff, // Bright cyan
      transparent: true,
      opacity: 0.7,
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });

    linkLine = new THREE.Line(lineGeometry, lineMaterial);
    linkLine.renderOrder = 999;
    scene.add(linkLine);
  } else {
    // Ensure attached to the active scene
    if (linkLine.parent !== scene) {
      scene.add(linkLine);
    }
    linkLine.visible = true;

    // Update vertex endpoints
    const posAttr = lineGeometry.attributes.position;
    posAttr.setXYZ(0, _posA.x, _posA.y, _posA.z);
    posAttr.setXYZ(1, _posB.x, _posB.y, _posB.z);
    posAttr.needsUpdate = true;
    lineGeometry.computeBoundingSphere();
  }

  // Pulsing opacity via sine wave for dynamic 'live link' aesthetic
  const time = performance.now() * 0.005;
  lineMaterial.opacity = 0.55 + 0.35 * Math.sin(time);
}
