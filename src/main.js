import { setupScene } from './sceneSetup.js';
import { loadAssets } from './loadAssets.js';
import { initializeOrbits, setupOrbitLines, updateSatellites } from './orbit.js';
import { setupUI, simulationSpeed } from './ui.js';

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

  // Bundle satellites into an array for the orbit updater
  const satellites = [satellite1, satellite2];

  // 3. Orbit visualisation lines (store references for toggle)
  const orbitLines = setupOrbitLines(scene);

  // 4. Orbit state machines
  const orbitStates = initializeOrbits();

  // 5. Setup UI Control Panel (Speed 1x/2x/4x & Orbit Lines Toggle)
  setupUI({
    onSpeedChange: (speed) => {
      console.log(`Simulation running at ${speed}× speed`);
    },
    onToggleOrbitLines: (visible) => {
      orbitLines.forEach((line) => {
        line.visible = visible;
      });
    }
  });

  // 6. Animation loop variables
  let lastTime = performance.now();

  function animate() {
    requestAnimationFrame(animate);

    const currentTime = performance.now();
    const deltaTime = (currentTime - lastTime) / 1000; // actual elapsed seconds
    lastTime = currentTime;

    // Simulation delta scaled by user-selected speed (1x, 2x, 4x)
    const simulationDelta = deltaTime * simulationSpeed;

    // Update camera controls (damping)
    controls.update();

    // Move satellites along their respective orbits using simulationDelta
    updateSatellites(satellites, orbitStates, simulationDelta);

    // Continuous slow Earth rotation around its own vertical axis
    if (earth) {
      earth.rotation.y += EARTH_ROTATION_SPEED * simulationDelta;
    }

    // Update real-time FPS display (unaffected by simulation speed)
    updateFpsCounter(currentTime);

    // Render current frame
    renderer.render(scene, camera);
  }

  // Start the render loop
  animate();
  console.log('🌍 Space environment simulation running with Earth rotation & UI controls');
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
