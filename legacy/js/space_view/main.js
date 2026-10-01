import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { GLTFSpecGlossExtension } from '../GLTFSpecGlossExtension.js';
import { OrbitState, setupOrbitLines } from '../orbit.js';

// ============================================================
// CONSTANTS & CONFIGURATION
// ============================================================

const EARTH_RADIUS = 10;
const EARTH_ROTATION_SPEED = 0.08; // rad/s
const SATELLITE_SCALE = 2.0;

// Camera defaults
const DEFAULT_GIMBAL_PAN = 90.0; // Pointing towards Earth (+X) initially
const DEFAULT_GIMBAL_TILT = 0.0;
const DEFAULT_CAMERA_FOV = 20.0;

// Math helpers
const _position = new THREE.Vector3();
const _targetQuat = new THREE.Quaternion();
const _tempVec = new THREE.Vector3();
const _frustum = new THREE.Frustum();
const _projScreenMatrix = new THREE.Matrix4();

// State variables
let currentPan = DEFAULT_GIMBAL_PAN;
let currentTilt = DEFAULT_GIMBAL_TILT;
let currentFov = DEFAULT_CAMERA_FOV;
let isPaused = false;
let simulationSpeed = 1.0;
let isReady = false;
let isTargetInFov = false;
let focusTarget = null; // null for Earth, or satellite Object3D

// Three.js Core Objects
let scene, mainCamera, renderer, controls;
let earthMesh = null;
let sat1Obj = null;
let sat2Obj = null;
let orbit1, orbit2;
let orbitLines = [];

// Gimbal & Virtual Camera Objects
let gimbalRigRoot = null;
let panGroup = null;
let tiltGroup = null;
let visualGimbalGroup = null;
let fovFrustumMesh = null;
let boresightRay = null;
let virtualCamera = null;
let virtualRenderTarget = null;

// PiP Canvas & Context
let pipCanvas = null;
let pipCtx = null;
let pipImageData = null;
let pipReadbackBuf = null;

// Reusable Frustum Geometry
let frustumGeo = null;
let frustumMat = null;

// ============================================================
// SCENE SETUP
// ============================================================

function initScene() {
  const container = document.getElementById('webgl-container');
  const width = window.innerWidth;
  const height = window.innerHeight;

  // Scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x020408);

  // Background stars / particle field
  createStarfield();

  // Main Camera
  mainCamera = new THREE.PerspectiveCamera(55, width / height, 0.1, 10000);
  mainCamera.position.set(34, 22, 40);

  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = false;
  container.appendChild(renderer.domElement);

  // OrbitControls
  controls = new OrbitControls(mainCamera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.minDistance = 12;
  controls.maxDistance = 250;
  controls.target.set(0, 0, 0);

  // Lighting
  const sunLight = new THREE.DirectionalLight(0xffffff, 3.2);
  sunLight.position.set(30, 15, 20);
  scene.add(sunLight);

  const fillLight = new THREE.DirectionalLight(0x60a5fa, 0.6);
  fillLight.position.set(-20, -10, -20);
  scene.add(fillLight);

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.35);
  scene.add(ambientLight);

  // Orbits
  const orbits = [
    new OrbitState(20, 0.3, 25, 0),
    new OrbitState(26, 0.2, 65, 180)
  ];
  orbit1 = orbits[0];
  orbit2 = orbits[1];
  orbitLines = setupOrbitLines(scene);

  // Virtual Camera & RenderTarget for Gimbal
  setupVirtualCamera();

  // Resize handler
  window.addEventListener('resize', onWindowResize);
}

function createStarfield() {
  const starCount = 1200;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(starCount * 3);
  const colors = new Float32Array(starCount * 3);

  for (let i = 0; i < starCount; i++) {
    const r = 250 + Math.random() * 200;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);

    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    positions[i * 3 + 2] = r * Math.cos(phi);

    const brightness = 0.5 + Math.random() * 0.5;
    colors[i * 3] = brightness;
    colors[i * 3 + 1] = brightness * (0.9 + Math.random() * 0.1);
    colors[i * 3 + 2] = brightness * (0.95 + Math.random() * 0.05);
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 1.5,
    vertexColors: true,
    transparent: true,
    opacity: 0.85
  });

  const starfield = new THREE.Points(geometry, material);
  scene.add(starfield);
}

function onWindowResize() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  mainCamera.aspect = w / h;
  mainCamera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

// ============================================================
// ASSET NORMALIZATION & LOADING
// ============================================================

function normalizeModel(model, targetSize, label) {
  model.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(model);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);

  const largestDim = Math.max(size.x, size.y, size.z) || 1.0;
  model.position.set(-center.x, -center.y, -center.z);

  const wrapper = new THREE.Group();
  wrapper.name = label;
  wrapper.add(model);
  wrapper.scale.setScalar(targetSize / largestDim);
  return wrapper;
}

async function loadGlbAssets() {
  const loader = new GLTFLoader();
  loader.register((parser) => new GLTFSpecGlossExtension(parser));

  const baseUrl = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.BASE_URL) || './';
  const cleanBase = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;

  function loadOne(url, label) {
    return new Promise((resolve, reject) => {
      loader.load(
        url,
        (gltf) => resolve(gltf),
        undefined,
        (err) => {
          console.warn(`Failed loading ${url}, attempting fallback placeholder`, err);
          resolve(null);
        }
      );
    });
  }

  const [earthGltf, sat1Gltf, sat2Gltf] = await Promise.all([
    loadOne(`${cleanBase}assets/earth.glb`, 'Earth'),
    loadOne(`${cleanBase}assets/satellite.glb`, 'Satellite 1'),
    loadOne(`${cleanBase}assets/satellite2.glb`, 'Satellite 2')
  ]);

  // 1. Earth
  if (earthGltf && earthGltf.scene) {
    earthMesh = normalizeModel(earthGltf.scene, EARTH_RADIUS * 2, 'Earth');
  } else {
    // Fallback procedural Earth sphere
    const geo = new THREE.SphereGeometry(EARTH_RADIUS, 64, 64);
    const mat = new THREE.MeshStandardMaterial({
      color: 0x1d4ed8,
      roughness: 0.7,
      metalness: 0.1
    });
    earthMesh = new THREE.Mesh(geo, mat);
    earthMesh.name = 'Earth';
  }
  earthMesh.position.set(0, 0, 0);
  scene.add(earthMesh);

  // 2. Satellite 1 (Observer)
  if (sat1Gltf && sat1Gltf.scene) {
    sat1Obj = normalizeModel(sat1Gltf.scene, SATELLITE_SCALE * 2, 'Satellite 1');
  } else {
    // Procedural fallback satellite
    sat1Obj = createFallbackSatellite(0x38bdf8, 'Satellite 1');
  }
  scene.add(sat1Obj);

  // 3. Satellite 2 (Target with Beacon)
  if (sat2Gltf && sat2Gltf.scene) {
    sat2Obj = normalizeModel(sat2Gltf.scene, SATELLITE_SCALE * 2, 'Satellite 2');
  } else {
    sat2Obj = createFallbackSatellite(0xf59e0b, 'Satellite 2');
  }
  scene.add(sat2Obj);

  // Attach optical beacon to Satellite 2
  attachBeaconToSat2();

  // Attach Gimbal & FOV Frustum to Satellite 1
  setupGimbalOnSat1();

  // Hide loading overlay
  const overlay = document.getElementById('loading-overlay');
  if (overlay) {
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 400);
  }

  isReady = true;
  console.log('✅ SkyLock 3D Space Scene initialized successfully');
}

function createFallbackSatellite(colorHex, name) {
  const group = new THREE.Group();
  group.name = name;

  // Main bus
  const busGeo = new THREE.BoxGeometry(1.2, 0.8, 0.8);
  const busMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.8, roughness: 0.3 });
  const bus = new THREE.Mesh(busGeo, busMat);
  group.add(bus);

  // Solar panels
  const panelGeo = new THREE.BoxGeometry(2.4, 0.04, 0.7);
  const panelMat = new THREE.MeshStandardMaterial({ color: colorHex, metalness: 0.9, roughness: 0.2 });
  const panelL = new THREE.Mesh(panelGeo, panelMat);
  panelL.position.set(1.8, 0, 0);
  group.add(panelL);

  const panelR = new THREE.Mesh(panelGeo, panelMat);
  panelR.position.set(-1.8, 0, 0);
  group.add(panelR);

  return group;
}

function attachBeaconToSat2() {
  const beaconGroup = new THREE.Group();
  beaconGroup.name = 'OpticalBeacon';

  const beaconLight = new THREE.PointLight(0x38bdf8, 3.0, 40, 2);
  beaconLight.position.set(0, 0.5, 0);
  beaconGroup.add(beaconLight);

  const beaconGeo = new THREE.SphereGeometry(0.18, 16, 16);
  const beaconMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
  const beaconMesh = new THREE.Mesh(beaconGeo, beaconMat);
  beaconMesh.position.set(0, 0.5, 0);
  beaconGroup.add(beaconMesh);

  sat2Obj.add(beaconGroup);
}

// ============================================================
// GIMBAL & VIRTUAL CAMERA VISUALIZATION
// ============================================================

function setupGimbalOnSat1() {
  // Gimbal hierarchy lives in world space and syncs with Sat 1 to prevent parent scale distortion
  gimbalRigRoot = new THREE.Group();
  gimbalRigRoot.name = 'GimbalRigRoot';

  panGroup = new THREE.Group();
  panGroup.name = 'PanGroup';
  gimbalRigRoot.add(panGroup);

  tiltGroup = new THREE.Group();
  tiltGroup.name = 'TiltGroup';
  panGroup.add(tiltGroup);

  // Visual mechanical gimbal representation
  visualGimbalGroup = createVisualGimbalModel();
  tiltGroup.add(visualGimbalGroup);

  // 3D Camera FOV Frustum representation
  createFovFrustumMesh();
  tiltGroup.add(fovFrustumMesh);

  // Optical boresight ray
  const rayGeo = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(0, 0, -18)
  ]);
  const rayMat = new THREE.LineBasicMaterial({
    color: 0x38bdf8,
    transparent: true,
    opacity: 0.75,
    linewidth: 1.5
  });
  boresightRay = new THREE.Line(rayGeo, rayMat);
  tiltGroup.add(boresightRay);

  // Mount virtual camera at optic aperture
  virtualCamera.position.set(0, 0, 0);
  tiltGroup.add(virtualCamera);

  scene.add(gimbalRigRoot);

  applyGimbalPose(currentPan, currentTilt);
}

function createVisualGimbalModel() {
  const root = new THREE.Group();
  root.name = 'VisualGimbalModel';

  // Base mount ring on S-1
  const baseGeo = new THREE.CylinderGeometry(0.35, 0.4, 0.15, 24);
  const baseMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.8, roughness: 0.4 });
  const baseMesh = new THREE.Mesh(baseGeo, baseMat);
  baseMesh.position.set(0, -0.2, 0);
  root.add(baseMesh);

  // Yoke / fork arms
  const armGeo = new THREE.BoxGeometry(0.08, 0.35, 0.15);
  const armMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.7, roughness: 0.3 });

  const armL = new THREE.Mesh(armGeo, armMat);
  armL.position.set(0.3, 0.05, 0);
  root.add(armL);

  const armR = new THREE.Mesh(armGeo, armMat);
  armR.position.set(-0.3, 0.05, 0);
  root.add(armR);

  // Sensor head / camera cylinder (pointing along -Z)
  const headGeo = new THREE.CylinderGeometry(0.24, 0.24, 0.55, 24);
  headGeo.rotateX(Math.PI / 2);
  const headMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, metalness: 0.85, roughness: 0.25 });
  const headMesh = new THREE.Mesh(headGeo, headMat);
  headMesh.position.set(0, 0.15, -0.1);
  root.add(headMesh);

  // Cyan accent ring
  const ringGeo = new THREE.TorusGeometry(0.25, 0.02, 16, 32);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
  const ringMesh = new THREE.Mesh(ringGeo, ringMat);
  ringMesh.position.set(0, 0.15, -0.36);
  root.add(ringMesh);

  // Optic lens face
  const lensGeo = new THREE.CircleGeometry(0.22, 24);
  const lensMat = new THREE.MeshStandardMaterial({
    color: 0x0ea5e9,
    metalness: 0.95,
    roughness: 0.1,
    side: THREE.DoubleSide
  });
  const lensMesh = new THREE.Mesh(lensGeo, lensMat);
  lensMesh.position.set(0, 0.15, -0.38);
  root.add(lensMesh);

  return root;
}

function createFovFrustumMesh() {
  const farDist = 16.0;
  const aspect = 320 / 240;
  const halfFovRad = THREE.MathUtils.degToRad(currentFov / 2);
  const halfH = Math.tan(halfFovRad) * farDist;
  const halfW = halfH * aspect;

  const origin = new THREE.Vector3(0, 0, 0);
  const tl = new THREE.Vector3(-halfW, halfH, -farDist);
  const tr = new THREE.Vector3(halfW, halfH, -farDist);
  const br = new THREE.Vector3(halfW, -halfH, -farDist);
  const bl = new THREE.Vector3(-halfW, -halfH, -farDist);

  // Pyramid edges + Far rectangle loop + Crosshair
  const points = [
    // 4 edges from apex
    origin, tl,
    origin, tr,
    origin, br,
    origin, bl,
    // Far rectangle loop
    tl, tr,
    tr, br,
    br, bl,
    bl, tl,
    // Far center cross
    new THREE.Vector3(0, halfH * 0.4, -farDist), new THREE.Vector3(0, -halfH * 0.4, -farDist),
    new THREE.Vector3(-halfW * 0.4, 0, -farDist), new THREE.Vector3(halfW * 0.4, 0, -farDist)
  ];

  frustumGeo = new THREE.BufferGeometry().setFromPoints(points);
  frustumMat = new THREE.LineBasicMaterial({
    color: 0x38bdf8,
    transparent: true,
    opacity: 0.65,
    linewidth: 1.2
  });

  fovFrustumMesh = new THREE.LineSegments(frustumGeo, frustumMat);
  fovFrustumMesh.name = 'FovFrustumMesh';
}

function updateFovFrustumGeometry(fovDeg) {
  if (!fovFrustumMesh) return;
  const farDist = 16.0;
  const aspect = 260 / 195;
  const halfFovRad = THREE.MathUtils.degToRad(fovDeg / 2);
  const halfH = Math.tan(halfFovRad) * farDist;
  const halfW = halfH * aspect;

  const origin = new THREE.Vector3(0, 0, 0);
  const tl = new THREE.Vector3(-halfW, halfH, -farDist);
  const tr = new THREE.Vector3(halfW, halfH, -farDist);
  const br = new THREE.Vector3(halfW, -halfH, -farDist);
  const bl = new THREE.Vector3(-halfW, -halfH, -farDist);

  const points = [
    origin, tl,
    origin, tr,
    origin, br,
    origin, bl,
    tl, tr,
    tr, br,
    br, bl,
    bl, tl,
    new THREE.Vector3(0, halfH * 0.4, -farDist), new THREE.Vector3(0, -halfH * 0.4, -farDist),
    new THREE.Vector3(-halfW * 0.4, 0, -farDist), new THREE.Vector3(halfW * 0.4, 0, -farDist)
  ];

  fovFrustumMesh.geometry.dispose();
  fovFrustumMesh.geometry = new THREE.BufferGeometry().setFromPoints(points);

  if (virtualCamera) {
    virtualCamera.fov = fovDeg;
    virtualCamera.updateProjectionMatrix();
  }
}

function setupVirtualCamera() {
  virtualCamera = new THREE.PerspectiveCamera(currentFov, 260 / 195, 0.1, 5000);

  virtualRenderTarget = new THREE.WebGLRenderTarget(260, 195, {
    minFilter: THREE.LinearFilter,
    magFilter: THREE.LinearFilter,
    format: THREE.RGBAFormat,
    type: THREE.UnsignedByteType,
    colorSpace: THREE.SRGBColorSpace
  });

  pipCanvas = document.getElementById('pip-canvas');
  if (pipCanvas) {
    pipCtx = pipCanvas.getContext('2d', { willReadFrequently: true });
    pipImageData = pipCtx.createImageData(260, 195);
    pipReadbackBuf = new Uint8Array(260 * 195 * 4);
  }
}

function applyGimbalPose(panDeg, tiltDeg) {
  currentPan = panDeg;
  currentTilt = tiltDeg;

  if (panGroup) {
    panGroup.rotation.y = THREE.MathUtils.degToRad(panDeg);
  }
  if (tiltGroup) {
    tiltGroup.rotation.x = THREE.MathUtils.degToRad(tiltDeg);
  }

  updatePipTelemetry();
}

// ============================================================
// ANIMATION & RENDER LOOP
// ============================================================

let lastTime = performance.now();
let frameCount = 0;
let lastFpsTime = performance.now();
let currentFps = 60;

function animate(now) {
  requestAnimationFrame(animate);

  const dt = Math.min((now - lastTime) / 1000, 0.1);
  lastTime = now;

  // FPS calculation
  frameCount++;
  if (now - lastFpsTime >= 500) {
    currentFps = Math.round((frameCount * 1000) / (now - lastFpsTime));
    frameCount = 0;
    lastFpsTime = now;
    const hudFps = document.getElementById('hud-fps');
    if (hudFps) hudFps.textContent = `${currentFps} FPS`;
  }

  const effectiveDt = isPaused ? 0 : dt * simulationSpeed;

  // 1. Earth rotation
  if (earthMesh && effectiveDt > 0) {
    earthMesh.rotation.y += EARTH_ROTATION_SPEED * effectiveDt;
  }

  // 2. Update Satellites along Orbits
  if (sat1Obj && orbit1 && effectiveDt > 0) {
    orbit1.update(effectiveDt);
    orbit1.getPosition(_position);
    sat1Obj.position.copy(_position);
    orbit1.getOrientation(_targetQuat);
    sat1Obj.quaternion.copy(_targetQuat);
  }

  if (sat2Obj && orbit2 && effectiveDt > 0) {
    orbit2.update(effectiveDt);
    orbit2.getPosition(_position);
    sat2Obj.position.copy(_position);
    orbit2.getOrientation(_targetQuat);
    sat2Obj.quaternion.copy(_targetQuat);
  }

  // 3. Sync Gimbal Rig Root to Sat 1 world pose
  if (gimbalRigRoot && sat1Obj) {
    gimbalRigRoot.position.copy(sat1Obj.position);
    gimbalRigRoot.quaternion.copy(sat1Obj.quaternion);
  }

  // 4. Update Camera FOV & Target Containment Test
  checkTargetInCameraFov();

  // 5. Update OrbitControls & Focus
  if (focusTarget) {
    controls.target.lerp(focusTarget.position, 0.08);
  }
  controls.update();

  // 6. Render Virtual Camera Feed to RenderTarget & blit to PiP
  renderVirtualFeed();

  // 7. Render Main 3D View
  renderer.setRenderTarget(null);
  renderer.render(scene, mainCamera);
}

function checkTargetInCameraFov() {
  if (!virtualCamera || !sat2Obj) return;

  virtualCamera.updateMatrixWorld();
  _projScreenMatrix.multiplyMatrices(virtualCamera.projectionMatrix, virtualCamera.matrixWorldInverse);
  _frustum.setFromProjectionMatrix(_projScreenMatrix);

  sat2Obj.getWorldPosition(_tempVec);
  const inFov = _frustum.containsPoint(_tempVec);

  if (inFov !== isTargetInFov) {
    isTargetInFov = inFov;
    if (frustumMat) {
      // Emerald green when target is in FOV, sky blue when searching
      frustumMat.color.setHex(inFov ? 0x22c55e : 0x38bdf8);
      frustumMat.opacity = inFov ? 0.95 : 0.65;
    }
    updatePipTelemetry();
  }
}

function renderVirtualFeed() {
  if (!virtualCamera || !virtualRenderTarget || !pipCtx) return;

  // Temporarily hide frustum and boresight from virtual camera's own feed
  if (fovFrustumMesh) fovFrustumMesh.visible = false;
  if (boresightRay) boresightRay.visible = false;

  renderer.setRenderTarget(virtualRenderTarget);
  renderer.render(scene, virtualCamera);
  renderer.setRenderTarget(null);

  if (fovFrustumMesh) fovFrustumMesh.visible = true;
  if (boresightRay) boresightRay.visible = true;

  // Read pixels and blit to PiP 2D canvas (with vertical flip)
  renderer.readRenderTargetPixels(virtualRenderTarget, 0, 0, 260, 195, pipReadbackBuf);

  const src = pipReadbackBuf;
  const dst = pipImageData.data;
  const w = 260;
  const h = 195;

  for (let y = 0; y < h; y++) {
    const srcRow = (h - 1 - y) * w * 4;
    const dstRow = y * w * 4;
    for (let x = 0; x < w * 4; x += 4) {
      dst[dstRow + x] = src[srcRow + x];
      dst[dstRow + x + 1] = src[srcRow + x + 1];
      dst[dstRow + x + 2] = src[srcRow + x + 2];
      dst[dstRow + x + 3] = 255;
    }
  }

  pipCtx.putImageData(pipImageData, 0, 0);
}

function updatePipTelemetry() {
  const anglesEl = document.getElementById('pip-angles');
  if (anglesEl) {
    const signP = currentPan >= 0 ? '+' : '';
    const signT = currentTilt >= 0 ? '+' : '';
    anglesEl.textContent = `PAN: ${signP}${currentPan.toFixed(1)}° | TILT: ${signT}${currentTilt.toFixed(1)}° | FOV: ${currentFov.toFixed(1)}°`;
  }

  const statusEl = document.getElementById('pip-target-status');
  if (statusEl) {
    if (isTargetInFov) {
      statusEl.textContent = 'TARGET: IN FOV';
      statusEl.className = 'status-in-fov';
    } else {
      statusEl.textContent = 'TARGET: OUT OF FOV';
      statusEl.className = 'status-out-fov';
    }
  }
}

// ============================================================
// UI CONTROLS & EVENT WIREUP
// ============================================================

function setupUIHandlers() {
  const btnReset = document.getElementById('btn-reset-cam');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      focusTarget = null;
      controls.target.set(0, 0, 0);
      mainCamera.position.set(34, 22, 40);
    });
  }

  const btnFocusS1 = document.getElementById('btn-focus-s1');
  if (btnFocusS1) {
    btnFocusS1.addEventListener('click', () => {
      if (sat1Obj) focusTarget = sat1Obj;
    });
  }

  const btnFocusS2 = document.getElementById('btn-focus-s2');
  if (btnFocusS2) {
    btnFocusS2.addEventListener('click', () => {
      if (sat2Obj) focusTarget = sat2Obj;
    });
  }

  const btnCollapse = document.getElementById('btn-pip-collapse');
  const pipContainer = document.getElementById('pip-container');
  if (btnCollapse && pipContainer) {
    btnCollapse.addEventListener('click', () => {
      pipContainer.classList.toggle('collapsed');
      btnCollapse.textContent = pipContainer.classList.contains('collapsed') ? '+' : '−';
    });
  }
}

// ============================================================
// PYTHON ↔ 3D JAVASCRIPT BRIDGE
// ============================================================

window.skylock3d = {
  isReady: () => isReady,

  setGimbalPose: (panDeg, tiltDeg) => {
    applyGimbalPose(Number(panDeg), Number(tiltDeg));
  },

  setCameraFov: (fovDeg) => {
    currentFov = Number(fovDeg);
    updateFovFrustumGeometry(currentFov);
    updatePipTelemetry();
  },

  updateState: (state) => {
    if (!state) return;
    if (state.pan !== undefined && state.tilt !== undefined) {
      applyGimbalPose(Number(state.pan), Number(state.tilt));
    }
    if (state.fov !== undefined) {
      currentFov = Number(state.fov);
      updateFovFrustumGeometry(currentFov);
    }
    if (state.paused !== undefined) {
      isPaused = Boolean(state.paused);
    }
    if (state.speed !== undefined) {
      simulationSpeed = Number(state.speed);
    }
    updatePipTelemetry();
  },

  setPaused: (paused) => {
    isPaused = Boolean(paused);
  },

  setSimulationSpeed: (speed) => {
    simulationSpeed = Number(speed);
  },

  resetView: () => {
    focusTarget = null;
    if (controls) controls.target.set(0, 0, 0);
    if (mainCamera) mainCamera.position.set(34, 22, 40);
  },

  getState: () => {
    const s1Pos = sat1Obj ? { x: sat1Obj.position.x, y: sat1Obj.position.y, z: sat1Obj.position.z } : null;
    const s2Pos = sat2Obj ? { x: sat2Obj.position.x, y: sat2Obj.position.y, z: sat2Obj.position.z } : null;
    return {
      ready: isReady,
      pan: currentPan,
      tilt: currentTilt,
      fov: currentFov,
      targetInFov: isTargetInFov,
      fps: currentFps,
      paused: isPaused,
      speed: simulationSpeed,
      satellite1: s1Pos,
      satellite2: s2Pos
    };
  }
};

// ============================================================
// BOOTSTRAP
// ============================================================

initScene();
setupUIHandlers();
loadGlbAssets().catch((err) => console.error('Asset load error:', err));
requestAnimationFrame(animate);
