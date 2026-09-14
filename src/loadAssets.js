import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';

// ============================================================
// TWEAKABLE CONSTANTS
// ============================================================

/** Earth will be normalized so its largest dimension equals this diameter. */
export const EARTH_RADIUS = 10;

/** Each satellite's largest dimension will be normalized to this diameter. */
export const SATELLITE_SIZE = 2.0;

/**
 * Set to true to get verbose bounding-box / mesh / triangle logging.
 * Set to false for a clean console in the final demo.
 */
const DEBUG_MODE = true;

// ============================================================
// HELPERS
// ============================================================

/**
 * Traverse every Mesh inside `root` and return aggregate stats.
 */
function collectMeshStats(root) {
  let meshCount = 0;
  let triangleCount = 0;

  root.traverse((child) => {
    if (child.isMesh && child.geometry) {
      meshCount++;

      const geo = child.geometry;
      if (geo.index) {
        // Indexed geometry — triangle count comes from the index buffer
        triangleCount += geo.index.count / 3;
      } else {
        // Non-indexed — every 3 vertices form a triangle
        const pos = geo.attributes.position;
        if (pos) {
          triangleCount += pos.count / 3;
        }
      }
    }
  });

  return { meshCount, triangleCount: Math.floor(triangleCount) };
}

/**
 * Normalize a loaded GLTF scene so that:
 *   1. Its visual bounding-box center sits at (0,0,0).
 *   2. Its largest dimension equals `targetSize`.
 *
 * Returns a wrapper THREE.Group that you add to the scene.
 *
 * Implementation note — we wrap the model inside an outer Group so that
 * the centering offset (applied to the inner model's position) and the
 * uniform scale (applied to the outer group) don't interfere with each
 * other.  The old code subtracted the native-unit center from model.position
 * and THEN set scale, which meant the world-space offset was
 * `center * scale` instead of `center`.
 */
function normalizeModel(model, targetSize, label) {
  // Force a world-matrix update before measuring
  model.updateMatrixWorld(true);

  const box = new THREE.Box3().setFromObject(model);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();

  box.getSize(size);
  box.getCenter(center);

  const largestDim = Math.max(size.x, size.y, size.z);

  // ---- Warn about suspicious dimensions ----
  if (largestDim === 0) {
    console.warn(`⚠️  ${label}: bounding-box largest dimension is 0 — model may have no visible geometry`);
  }
  if (!isFinite(largestDim)) {
    console.warn(`⚠️  ${label}: bounding-box largest dimension is Infinity — model hierarchy may be corrupt`);
  }
  if (largestDim < 1e-6 && largestDim !== 0) {
    console.warn(`⚠️  ${label}: bounding-box largest dimension is extremely small (${largestDim}) — geometry may be degenerate`);
  }
  if (largestDim > 1e6) {
    console.warn(`⚠️  ${label}: bounding-box largest dimension is extremely large (${largestDim})`);
  }

  // ---- Center the model so its bounding-box mid-point is at the origin ----
  model.position.set(-center.x, -center.y, -center.z);

  // ---- Wrap in an outer Group and scale that ----
  const wrapper = new THREE.Group();
  wrapper.name = label;
  wrapper.add(model);

  const scale = targetSize / largestDim;
  wrapper.scale.setScalar(scale);

  // ---- Debug logging ----
  if (DEBUG_MODE) {
    const stats = collectMeshStats(model);
    console.group(`📦 ${label}`);
    console.log(`Meshes       : ${stats.meshCount}`);
    console.log(`Triangles    : ${stats.triangleCount.toLocaleString()}`);
    console.log(`Native BB min: (${box.min.x.toFixed(2)}, ${box.min.y.toFixed(2)}, ${box.min.z.toFixed(2)})`);
    console.log(`Native BB max: (${box.max.x.toFixed(2)}, ${box.max.y.toFixed(2)}, ${box.max.z.toFixed(2)})`);
    console.log(`Native size  : (${size.x.toFixed(2)}, ${size.y.toFixed(2)}, ${size.z.toFixed(2)})`);
    console.log(`Native center: (${center.x.toFixed(2)}, ${center.y.toFixed(2)}, ${center.z.toFixed(2)})`);
    console.log(`Largest dim  : ${largestDim.toFixed(4)}`);
    console.log(`Target size  : ${targetSize}`);
    console.log(`Scale factor : ${scale.toFixed(6)}`);

    // Material diagnostics
    let meshIdx = 0;
    model.traverse((child) => {
      if (child.isMesh) {
        const mat = child.material;
        const hasMap = !!(mat.map);
        const hasNormal = !!(mat.normalMap);
        const hasEmissive = !!(mat.emissiveMap);
        const col = mat.color ? `#${mat.color.getHexString()}` : 'none';
        console.log(
          `  Mesh ${meshIdx}: type=${mat.type}, color=${col}, map=${hasMap}, normalMap=${hasNormal}, emissiveMap=${hasEmissive}, metalness=${mat.metalness ?? '-'}, roughness=${mat.roughness ?? '-'}`
        );
        meshIdx++;
      }
    });
    console.groupEnd();
  }

  // ---- Verify final world-space size ----
  wrapper.updateMatrixWorld(true);
  const finalBox = new THREE.Box3().setFromObject(wrapper);
  const finalSize = new THREE.Vector3();
  finalBox.getSize(finalSize);

  if (DEBUG_MODE) {
    console.log(
      `${label} final world size: (${finalSize.x.toFixed(2)}, ${finalSize.y.toFixed(2)}, ${finalSize.z.toFixed(2)})  largest = ${Math.max(finalSize.x, finalSize.y, finalSize.z).toFixed(2)}`
    );
  }

  // Enable shadows on every mesh
  model.traverse((child) => {
    if (child.isMesh) {
      child.castShadow = true;
      child.receiveShadow = true;
    }
  });

  return wrapper;
}

// ============================================================
// PUBLIC API
// ============================================================

/**
 * Load Earth + two satellites, normalize them, add to `scene`.
 *
 * Returns `{ earth, satellite1, satellite2 }`.
 */
export async function loadAssets(scene) {
  const loader = new GLTFLoader();

  // Setup DRACO decoder for compressed meshes (if any)
  const dracoLoader = new DRACOLoader();
  dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.7/');
  loader.setDRACOLoader(dracoLoader);

  /**
   * Promise-based GLB loader with clear success/error logging.
   */
  function loadGLB(url, label) {
    console.log(`⏳ Loading ${label} from ${url} …`);

    return new Promise((resolve, reject) => {
      loader.load(
        url,
        (gltf) => {
          console.log(`✅ ${label} loaded successfully`, gltf);
          resolve(gltf);
        },
        undefined,
        (error) => {
          console.error(`❌ FAILED TO LOAD ${label}:`, error);
          reject(new Error(`Failed to load ${label}: ${error.message || error}`));
        }
      );
    });
  }

  // ------------------------------------------------------------------
  // Load all three GLBs in parallel
  // ------------------------------------------------------------------
  const [earthGltf, sat1Gltf, sat2Gltf] = await Promise.all([
    loadGLB('/assets/earth.glb', 'Earth'),
    loadGLB('/assets/satellite.glb', 'Satellite 1'),
    loadGLB('/assets/satellite2.glb', 'Satellite 2'),
  ]);

  // ------------------------------------------------------------------
  // Earth — normalize to diameter = EARTH_RADIUS * 2
  // ------------------------------------------------------------------
  const earth = normalizeModel(earthGltf.scene, EARTH_RADIUS * 2, 'Earth');
  earth.position.set(0, 0, 0);
  scene.add(earth);

  // ------------------------------------------------------------------
  // Satellite 1 — normalize to diameter = SATELLITE_SIZE * 2
  // ------------------------------------------------------------------
  const satellite1 = normalizeModel(sat1Gltf.scene, SATELLITE_SIZE * 2, 'Satellite 1');
  scene.add(satellite1);

  // ------------------------------------------------------------------
  // Satellite 2 — loaded from a separate file, normalized independently
  // ------------------------------------------------------------------
  const satellite2 = normalizeModel(sat2Gltf.scene, SATELLITE_SIZE * 2, 'Satellite 2');
  scene.add(satellite2);

  // ------------------------------------------------------------------
  console.log('🚀 All assets loaded and normalized');

  return { earth, satellite1, satellite2 };
}
