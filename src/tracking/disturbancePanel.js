import { disturbances } from './disturbances.js';

/**
 * Disturbance Panel Controller.
 * Manages UI controls for preset switching, live parameter sliders, seed input,
 * and collapsible display.
 */

let panelEl = null;
let bodyEl = null;
let collapseBtn = null;
let seedDisplayEl = null;

// Preset buttons
const presetBtns = {};

// Slider and readout elements
const sliderMap = {
  wanderRmsPx: { sliderId: 'dist-slider-wander', labelId: 'dist-val-wander', format: (v) => `${Number(v).toFixed(1)} px` },
  scintillationSigma: { sliderId: 'dist-slider-scint', labelId: 'dist-val-scint', format: (v) => Number(v).toFixed(2) },
  jitterRmsDeg: { sliderId: 'dist-slider-jitter', labelId: 'dist-val-jitter', format: (v) => `${Number(v).toFixed(2)}°` },
  noiseSigma: { sliderId: 'dist-slider-noise', labelId: 'dist-val-noise', format: (v) => `${Math.round(v)} LSB` },
  hotPixelsCount: { sliderId: 'dist-slider-hot', labelId: 'dist-val-hot', format: (v) => `${Math.round(v)}` },
  blurRadiusPx: { sliderId: 'dist-slider-blur', labelId: 'dist-val-blur', format: (v) => `${Math.round(v)} px` },
  dropProbability: { sliderId: 'dist-slider-drop', labelId: 'dist-val-drop', format: (v) => `${(Number(v) * 100).toFixed(0)}%` }
};

/**
 * Synchronize UI elements with current disturbance parameters and preset.
 */
export function syncDisturbanceUI() {
  const currentPreset = disturbances.getPreset();
  const params = disturbances.getParams();

  // Update preset button active classes
  Object.keys(presetBtns).forEach((name) => {
    const btn = presetBtns[name];
    if (btn) {
      if (name.toUpperCase() === currentPreset.toUpperCase()) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    }
  });

  // Update sliders and labels
  Object.keys(sliderMap).forEach((key) => {
    const conf = sliderMap[key];
    const slider = document.getElementById(conf.sliderId);
    const label = document.getElementById(conf.labelId);
    const val = params[key] !== undefined ? params[key] : 0;

    if (slider) {
      slider.value = val;
    }
    if (label) {
      label.textContent = conf.format(val);
    }
  });

  // Update seed display
  if (seedDisplayEl) {
    seedDisplayEl.textContent = `SEED: ${disturbances.getSeed()}`;
  }
}

/**
 * Initialize disturbance panel DOM event listeners and state.
 */
export function initDisturbancePanel() {
  panelEl = document.getElementById('disturbance-panel');
  if (!panelEl) return;

  bodyEl = document.getElementById('disturbance-panel-body');
  collapseBtn = document.getElementById('disturbance-collapse-btn');
  seedDisplayEl = document.getElementById('dist-seed-display');

  // Collapse / expand toggle
  if (collapseBtn && bodyEl) {
    collapseBtn.addEventListener('click', () => {
      const isHidden = bodyEl.style.display === 'none';
      bodyEl.style.display = isHidden ? 'flex' : 'none';
      collapseBtn.textContent = isHidden ? '−' : '+';
    });
  }

  // Presets wiring
  ['OFF', 'LOW', 'MED', 'HIGH'].forEach((name) => {
    const btn = document.getElementById(`dist-btn-${name.toLowerCase()}`);
    if (btn) {
      presetBtns[name] = btn;
      btn.addEventListener('click', () => {
        disturbances.setPreset(name);
        syncDisturbanceUI();
      });
    }
  });

  // Sliders wiring
  Object.keys(sliderMap).forEach((key) => {
    const conf = sliderMap[key];
    const slider = document.getElementById(conf.sliderId);
    if (slider) {
      slider.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        disturbances.setParam(key, val);
        syncDisturbanceUI();
      });
    }
  });

  // Random seed button
  const seedBtn = document.getElementById('dist-seed-random-btn');
  if (seedBtn) {
    seedBtn.addEventListener('click', () => {
      const newSeed = Math.floor(Math.random() * 900000) + 10000;
      disturbances.setSeed(newSeed);
      syncDisturbanceUI();
    });
  }

  syncDisturbanceUI();
}
