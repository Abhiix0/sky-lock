/**
 * UI Control Panel Module for Sky Lock Space Environment Simulation
 */

export const SIMULATION_SPEEDS = [1, 2, 4];
export let simulationSpeed = 1;
export let orbitLinesVisible = true;

/**
 * Initialize control panel buttons and event handlers.
 * 
 * @param {Object} options
 * @param {Function} options.onSpeedChange - Callback when simulation speed changes (e.g. (speed) => ...)
 * @param {Function} options.onToggleOrbitLines - Callback when orbit lines visibility toggles (e.g. (visible) => ...)
 */
export function setupUI({ onSpeedChange, onToggleOrbitLines }) {
  // Speed buttons
  const speedButtons = document.querySelectorAll('.speed-btn');

  speedButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const speed = parseFloat(btn.getAttribute('data-speed'));
      if (isNaN(speed)) return;

      simulationSpeed = speed;

      // Update active button styling
      speedButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      console.log(`Simulation Speed set to: ${speed}×`);

      if (typeof onSpeedChange === 'function') {
        onSpeedChange(speed);
      }
    });
  });

  // Orbit lines toggle button
  const toggleBtn = document.getElementById('orbit-lines-toggle');

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      orbitLinesVisible = !orbitLinesVisible;

      if (orbitLinesVisible) {
        toggleBtn.textContent = 'ON';
        toggleBtn.classList.remove('off');
        toggleBtn.classList.add('on');
      } else {
        toggleBtn.textContent = 'OFF';
        toggleBtn.classList.remove('on');
        toggleBtn.classList.add('off');
      }

      console.log(`Orbit Lines: ${orbitLinesVisible ? 'ON' : 'OFF'}`);

      if (typeof onToggleOrbitLines === 'function') {
        onToggleOrbitLines(orbitLinesVisible);
      }
    });
  }
}
