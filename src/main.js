import { setupScene } from './sceneSetup.js';
import { loadAssets } from './loadAssets.js';
import { initializeOrbits, setupOrbitLines, updateSatellites } from './orbit.js';

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
// MAIN
// ============================================================

async function main() {
  // 1. Scene, camera, renderer, controls
  const { scene, camera, renderer, controls } = setupScene();

  // 2. Load all GLB assets (Earth + 2 satellites)
  const { earth, satellite1, satellite2 } = await loadAssets(scene);

  // Bundle satellites into an array for the orbit updater
  const satellites = [satellite1, satellite2];

  // 3. Orbit visualisation lines
  setupOrbitLines(scene);

  // 4. Orbit state machines
  const orbitStates = initializeOrbits();

  // 5. Animation loop
  let lastTime = performance.now();

  function animate() {
    requestAnimationFrame(animate);

    const currentTime = performance.now();
    const deltaTime = (currentTime - lastTime) / 1000; // seconds
    lastTime = currentTime;

    // Update camera controls
    controls.update();

    // Move satellites along their orbits
    updateSatellites(satellites, orbitStates, deltaTime);

    // Gentle Earth rotation for visual interest
    if (earth) {
      earth.rotation.y += 0.01 * deltaTime;
    }

    // FPS display
    updateFpsCounter(currentTime);

    // Render
    renderer.render(scene, camera);
  }

  animate();
  console.log('🌍 Space environment simulation running');
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
