import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

// ============================================================
// TWEAKABLE SCENE CONSTANTS
// ============================================================

export const CAMERA_FOV = 60;
export const CAMERA_NEAR = 0.1;
export const CAMERA_FAR = 10000;

// Position chosen to frame Earth (diameter 20) + orbits (radius up to 26)
export const CAMERA_INITIAL_POSITION = { x: 32, y: 24, z: 38 };

// Lighting
export const SUN_INTENSITY = 3.0;
export const SUN_POSITION = { x: 20, y: 10, z: 15 };
export const AMBIENT_INTENSITY = 0.15;

/**
 * Initialize the Three.js scene, camera, renderer, and lighting.
 */
export function setupScene() {
  // ---- Scene ----
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);

  // ---- Camera ----
  const camera = new THREE.PerspectiveCamera(
    CAMERA_FOV,
    window.innerWidth / window.innerHeight,
    CAMERA_NEAR,
    CAMERA_FAR
  );
  camera.position.set(
    CAMERA_INITIAL_POSITION.x,
    CAMERA_INITIAL_POSITION.y,
    CAMERA_INITIAL_POSITION.z
  );

  // ---- Renderer ----
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  document.getElementById('canvas-container').appendChild(renderer.domElement);

  // ---- Orbit controls ----
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.enablePan = false;
  controls.target.set(0, 0, 0);
  controls.minDistance = 15;
  controls.maxDistance = 300;

  // ---- Lighting ----
  setupLighting(scene);

  // ---- Window resize ----
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  return { scene, camera, renderer, controls };
}

/**
 * Setup scene lighting.
 */
function setupLighting(scene) {
  // Directional light (Sun)
  const sunLight = new THREE.DirectionalLight(0xffffff, SUN_INTENSITY);
  sunLight.position.set(SUN_POSITION.x, SUN_POSITION.y, SUN_POSITION.z);
  sunLight.castShadow = true;

  // Shadow camera
  sunLight.shadow.mapSize.width = 2048;
  sunLight.shadow.mapSize.height = 2048;
  sunLight.shadow.camera.near = 0.5;
  sunLight.shadow.camera.far = 500;
  sunLight.shadow.camera.left = -100;
  sunLight.shadow.camera.right = 100;
  sunLight.shadow.camera.top = 100;
  sunLight.shadow.camera.bottom = -100;

  scene.add(sunLight);

  // Ambient light (so the dark side isn't completely black)
  const ambientLight = new THREE.AmbientLight(0xffffff, AMBIENT_INTENSITY);
  scene.add(ambientLight);
}
