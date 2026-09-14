import * as THREE from 'three';
import { MIN_SATELLITE_DISTANCE, MAX_SATELLITE_DISTANCE, MAX_MANUAL_SATELLITES } from './orbit.js';

/**
 * UI Control Panel Module for Sky Lock Space Environment Simulation
 */

export const SIMULATION_SPEEDS = [1, 2, 4];
export let simulationSpeed = 1;
export let orbitLinesVisible = true;
export let isPaused = false;
export let satelliteMode = 'AUTOMATIC'; // 'AUTOMATIC' | 'MANUAL'

// Mini 3D preview variables
let previewRenderer = null;
let previewScene = null;
let previewCamera = null;
let previewModel = null;
let isPreviewInitialized = false;

/**
 * Initialize 3D mini-preview of the actual satellite GLB inside the control panel.
 */
export function initSatellitePreview(sourceSatelliteModel) {
  const previewCanvas = document.getElementById('satellite-preview-canvas');
  if (!previewCanvas || isPreviewInitialized) return;

  previewRenderer = new THREE.WebGLRenderer({
    canvas: previewCanvas,
    alpha: true,
    antialias: true
  });
  previewRenderer.setSize(140, 90);
  previewRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  previewScene = new THREE.Scene();
  previewCamera = new THREE.PerspectiveCamera(40, 140 / 90, 0.1, 100);
  previewCamera.position.set(0, 1.2, 4.0);
  previewCamera.lookAt(0, 0, 0);

  const previewSun = new THREE.DirectionalLight(0xffffff, 2.8);
  previewSun.position.set(5, 5, 5);
  previewScene.add(previewSun);
  previewScene.add(new THREE.AmbientLight(0xffffff, 0.4));

  // Clone from the actual loaded satellite model
  previewModel = sourceSatelliteModel.clone(true);
  previewModel.scale.setScalar(0.7);
  previewModel.position.set(0, 0, 0);
  previewScene.add(previewModel);

  isPreviewInitialized = true;
}

/**
 * Animate the 3D preview gently inside the manual control panel.
 */
export function renderSatellitePreview() {
  if (!isPreviewInitialized || satelliteMode !== 'MANUAL' || !previewModel) return;
  previewModel.rotation.y += 0.015;
  previewRenderer.render(previewScene, previewCamera);
}

/**
 * Setup UI control panel, event handlers, and drag-and-drop interaction.
 */
export function setupUI({
  onSpeedChange,
  onToggleOrbitLines,
  onTogglePause,
  onModeChange,
  onDropSatellite,
  getManualCount,
  camera,
  scene,
  controls,
  ghostModelTemplate
}) {
  // 1. Speed Buttons
  const speedButtons = document.querySelectorAll('.speed-btn');
  speedButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const speed = parseFloat(btn.getAttribute('data-speed'));
      if (isNaN(speed)) return;

      simulationSpeed = speed;
      speedButtons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      if (typeof onSpeedChange === 'function') {
        onSpeedChange(speed);
      }
    });
  });

  // 2. Orbit Lines Toggle
  const orbitToggleBtn = document.getElementById('orbit-lines-toggle');
  if (orbitToggleBtn) {
    orbitToggleBtn.addEventListener('click', () => {
      orbitLinesVisible = !orbitLinesVisible;

      if (orbitLinesVisible) {
        orbitToggleBtn.textContent = 'ON';
        orbitToggleBtn.classList.remove('off');
        orbitToggleBtn.classList.add('on');
      } else {
        orbitToggleBtn.textContent = 'OFF';
        orbitToggleBtn.classList.remove('on');
        orbitToggleBtn.classList.add('off');
      }

      if (typeof onToggleOrbitLines === 'function') {
        onToggleOrbitLines(orbitLinesVisible);
      }
    });
  }

  // 3. Pause / Resume Toggle
  const pauseToggleBtn = document.getElementById('pause-toggle');
  if (pauseToggleBtn) {
    pauseToggleBtn.addEventListener('click', () => {
      isPaused = !isPaused;

      if (isPaused) {
        pauseToggleBtn.textContent = 'RESUME';
        pauseToggleBtn.classList.add('paused');
      } else {
        pauseToggleBtn.textContent = 'PAUSE';
        pauseToggleBtn.classList.remove('paused');
      }

      if (typeof onTogglePause === 'function') {
        onTogglePause(isPaused);
      }
    });
  }

  // 4. Satellite Mode Selector
  const modeAutoBtn = document.getElementById('mode-auto');
  const modeManualBtn = document.getElementById('mode-manual');
  const manualSection = document.getElementById('manual-satellite-section');

  function setMode(mode) {
    satelliteMode = mode;

    if (mode === 'AUTOMATIC') {
      modeAutoBtn.classList.add('active');
      modeManualBtn.classList.remove('active');
      if (manualSection) manualSection.style.display = 'none';
    } else {
      modeManualBtn.classList.add('active');
      modeAutoBtn.classList.remove('active');
      if (manualSection) manualSection.style.display = 'block';
    }

    if (typeof onModeChange === 'function') {
      onModeChange(mode);
    }
  }

  if (modeAutoBtn) {
    modeAutoBtn.addEventListener('click', () => setMode('AUTOMATIC'));
  }
  if (modeManualBtn) {
    modeManualBtn.addEventListener('click', () => setMode('MANUAL'));
  }

  // 5. Drag-and-Drop Placement from Simulation Panel into 3D Scene
  const previewContainer = document.getElementById('satellite-preview-container');
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  const dropPoint = new THREE.Vector3();
  const planeNormal = new THREE.Vector3();
  const plane = new THREE.Plane();

  let isDragging = false;
  let ghostSatellite = null;

  function createGhostSatellite() {
    if (!ghostModelTemplate) return null;
    const ghost = ghostModelTemplate.clone(true);
    ghost.traverse((child) => {
      if (child.isMesh && child.material) {
        child.material = child.material.clone();
        child.material.transparent = true;
        child.material.opacity = 0.65;
        if (child.material.emissive) {
          child.material.emissive.setHex(0x00aaff);
        }
      }
    });
    ghost.visible = false;
    scene.add(ghost);
    return ghost;
  }

  if (previewContainer) {
    previewContainer.addEventListener('pointerdown', (e) => {
      // Allow only primary mouse button or touch
      if (e.button !== 0 && e.pointerType === 'mouse') return;

      // Check max manual satellites constraint
      const currentCount = typeof getManualCount === 'function' ? getManualCount() : 0;
      if (currentCount >= MAX_MANUAL_SATELLITES) {
        alert('Maximum 2 satellites allowed.');
        return;
      }

      isDragging = true;
      previewContainer.classList.add('dragging');

      // Temporarily disable orbit controls so dragging doesn't rotate camera
      if (controls) controls.enabled = false;

      // Instantiate or show ghost satellite in 3D scene
      if (!ghostSatellite) {
        ghostSatellite = createGhostSatellite();
      }
      if (ghostSatellite) {
        ghostSatellite.visible = true;
      }

      updateGhostPosition(e.clientX, e.clientY);
    });
  }

  function updateGhostPosition(clientX, clientY) {
    if (!isDragging || !ghostSatellite || !camera) return;

    mouse.x = (clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(clientY / window.innerHeight) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    // Plane passing through Earth (0,0,0) facing the camera
    camera.getWorldDirection(planeNormal).negate();
    plane.setFromNormalAndCoplanarPoint(planeNormal, new THREE.Vector3(0, 0, 0));

    const hit = raycaster.ray.intersectPlane(plane, dropPoint);
    if (hit) {
      // Clamp placement radius so satellite is never inside Earth
      let dist = dropPoint.length();
      if (dist < MIN_SATELLITE_DISTANCE) {
        dropPoint.normalize().multiplyScalar(MIN_SATELLITE_DISTANCE);
      } else if (dist > MAX_SATELLITE_DISTANCE) {
        dropPoint.normalize().multiplyScalar(MAX_SATELLITE_DISTANCE);
      }

      ghostSatellite.position.copy(dropPoint);
      ghostSatellite.lookAt(0, 0, 0);
    }
  }

  window.addEventListener('pointermove', (e) => {
    if (isDragging) {
      updateGhostPosition(e.clientX, e.clientY);
    }
  });

  window.addEventListener('pointerup', (e) => {
    if (!isDragging) return;

    isDragging = false;
    if (previewContainer) previewContainer.classList.remove('dragging');

    // Restore orbit controls
    if (controls) controls.enabled = true;

    // Hide ghost satellite
    if (ghostSatellite) {
      ghostSatellite.visible = false;
    }

    // Check if drop location is over the 3D viewport (not dropped inside the control panel)
    const panel = document.getElementById('control-panel');
    let droppedInPanel = false;
    if (panel) {
      const rect = panel.getBoundingClientRect();
      if (
        e.clientX >= rect.left &&
        e.clientX <= rect.right &&
        e.clientY >= rect.top &&
        e.clientY <= rect.bottom
      ) {
        droppedInPanel = true;
      }
    }

    if (!droppedInPanel && typeof onDropSatellite === 'function') {
      onDropSatellite(dropPoint.clone());
    }
  });
}
