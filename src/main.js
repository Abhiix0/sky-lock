import * as THREE from 'three';
import { setupScene } from './sceneSetup.js';
import { loadAssets } from './loadAssets.js';
import {
  initializeOrbits,
  setupOrbitLines,
  updateSatellites,
  createManualOrbit,
  updateManualSatellites,
  MAX_MANUAL_SATELLITES
} from './orbit.js';
import {
  setupUI,
  initSatellitePreview,
  renderSatellitePreview,
  simulationSpeed,
  isPaused,
  orbitLinesVisible,
  satelliteMode
} from './ui.js';

// ============================================================
// CONFIGURATION CONSTANTS
// ============================================================

/**
 * Earth continuous rotation speed (radians/second at 1x simulation speed).
 * Noticeably slower than satellite orbital movement.
 */
export const EARTH_ROTATION_SPEED = 0.08;

// ============================================================
// FPS COUNTER
// ============================================================

let frameCount = 0;
let lastFpsUpdate = 0;
const fpsUpdateInterval = 500; // ms

function updateFpsCounter(currentTime) {
  frameCount++;

  if (currentTime - lastFpsUpdate >= fpsUpdateInterval) {
    const fps = Math.round(frameCount / ((currentTime - lastFpsUpdate) / 1000));
    document.getElementById('fps-counter').textContent = `FPS: ${fps}`;
    frameCount = 0;
    lastFpsUpdate = currentTime;
  }
}

// ============================================================
// MAIN APPLICATION
// ============================================================

async function main() {
  // 1. Setup Three.js scene, camera, renderer, orbit controls
  const { scene, camera, renderer, controls } = setupScene();

  // 2. Load all GLB assets (Earth with Sketchfab textures + 2 satellites)
  const { earth, satellite1, satellite2 } = await loadAssets(scene);

  // Automatic mode satellites and orbits
  const autoSatellites = [satellite1, satellite2];
  const autoOrbitLines = setupOrbitLines(scene);
  const autoOrbitStates = initializeOrbits();

  // Manual mode satellites and orbits
  const manualSatellites = [];
  const manualOrbitStates = [];
  const manualOrbitLines = [];

  // Initialize the mini 3D satellite preview in the control panel
  initSatellitePreview(satellite1);

  // Function to create a manually placed satellite from user drop position
  function handleDropSatellite(dropPosition) {
    if (manualSatellites.length >= MAX_MANUAL_SATELLITES) {
      alert('Maximum 2 satellites allowed.');
      return;
    }

    const satIndex = manualSatellites.length;
    // 1st manual satellite uses satellite.glb, 2nd uses satellite2.glb
    const sourceModel = satIndex === 0 ? satellite1 : satellite2;
    const newSatellite = sourceModel.clone(true);

    // Enforce castShadow = false on all meshes of manual satellite
    newSatellite.traverse((child) => {
      if (child.isMesh) {
        child.castShadow = false;
      }
    });

    // Create elliptical orbit passing through dropPosition
    const { orbitState, orbitLine, initialPosition } = createManualOrbit(dropPosition, satIndex);

    newSatellite.position.copy(initialPosition);
    newSatellite.visible = true;
    orbitLine.visible = orbitLinesVisible;

    scene.add(newSatellite);
    scene.add(orbitLine);

    manualSatellites.push(newSatellite);
    manualOrbitStates.push(orbitState);
    manualOrbitLines.push(orbitLine);

    console.log(`Manual satellite ${satIndex + 1} placed at:`, initialPosition);
  }

  // Function to switch between AUTOMATIC and MANUAL satellite modes
  function handleModeChange(mode) {
    if (mode === 'AUTOMATIC') {
      // Restore automatic satellites and orbit lines
      autoSatellites.forEach((sat) => {
        sat.visible = true;
      });
      autoOrbitLines.forEach((line) => {
        line.visible = orbitLinesVisible;
      });

      // Hide manual satellites and manual orbit lines
      manualSatellites.forEach((sat) => {
        sat.visible = false;
      });
      manualOrbitLines.forEach((line) => {
        line.visible = false;
      });
    } else {
      // MANUAL MODE:
      // Hide automatic satellites and automatic orbit lines
      autoSatellites.forEach((sat) => {
        sat.visible = false;
      });
      autoOrbitLines.forEach((line) => {
        line.visible = false;
      });

      // Show manual satellites and manual orbit lines
      manualSatellites.forEach((sat) => {
        sat.visible = true;
      });
      manualOrbitLines.forEach((line) => {
        line.visible = orbitLinesVisible;
      });
    }
  }

  // 3. Setup UI Control Panel (Speed, Orbit Lines, Pause, Mode, Drag-and-Drop)
  setupUI({
    onSpeedChange: (speed) => {
      console.log(`Simulation running at ${speed}× speed`);
    },
    onToggleOrbitLines: (visible) => {
      if (satelliteMode === 'AUTOMATIC') {
        autoOrbitLines.forEach((line) => {
          line.visible = visible;
        });
      } else {
        manualOrbitLines.forEach((line) => {
          line.visible = visible;
        });
      }
    },
    onTogglePause: (paused) => {
      console.log(`Simulation ${paused ? 'PAUSED' : 'RESUMED'}`);
    },
    onModeChange: handleModeChange,
    onDropSatellite: handleDropSatellite,
    getManualCount: () => manualSatellites.length,
    camera,
    scene,
    controls,
    ghostModelTemplate: satellite1
  });

  // 4. Animation loop variables
  let lastTime = performance.now();

  function animate() {
    requestAnimationFrame(animate);

    const currentTime = performance.now();
    const deltaTime = (currentTime - lastTime) / 1000; // actual elapsed seconds
    lastTime = currentTime;

    // Simulation delta scaled by user-selected speed (1x, 2x, 4x), or 0 if paused
    const simulationDelta = isPaused ? 0 : deltaTime * simulationSpeed;

    // Update camera controls (damping)
    controls.update();

    // Update satellites according to active mode
    if (satelliteMode === 'AUTOMATIC') {
      updateSatellites(autoSatellites, autoOrbitStates, simulationDelta);
    } else {
      updateManualSatellites(manualSatellites, manualOrbitStates, simulationDelta);
    }

    // Continuous slow Earth rotation around its own vertical axis
    if (earth) {
      earth.rotation.y += EARTH_ROTATION_SPEED * simulationDelta;
    }

    // Render mini 3D preview in control panel if manual mode is active
    renderSatellitePreview();

    // Update real-time FPS display (unaffected by simulation speed or pause)
    updateFpsCounter(currentTime);

    // Render current frame
    renderer.render(scene, camera);
  }

  // Start the render loop
  animate();
  console.log('🌍 Space environment simulation running with Pause, Mode selector, and Manual Satellite Drag-and-Drop');
}

// ============================================================
// BOOTSTRAP
// ============================================================

main().catch((error) => {
  console.error('Failed to start application:', error);
  document.body.innerHTML = `
    <div style="color: #f00; padding: 20px; font-family: monospace;">
      <h2>Error Loading Application</h2>
      <pre>${error.message}</pre>
    </div>
  `;
});
