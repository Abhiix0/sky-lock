import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { GLTFSpecGlossExtension } from './GLTFSpecGlossExtension.js';

// ============================================================
// TWEAKABLE CONSTANTS
// ============================================================

/** Earth will be normalized so its largest dimension equals this diameter. */
export const EARTH_RADIUS = 10;

/** Each satellite's largest dimension will be normalized to this diameter. */
export const SATELLITE_SIZE = 2.0;

/**
 * Set to true to get verbose bounding-box / mesh / triangle logging.
 */
const DEBUG_MODE = false;

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
    console.warn(
      `⚠️  ${label}: bounding-box largest dimension is 0 — model may have no visible geometry`
    );
  }
  if (!isFinite(largestDim)) {
    console.warn(
      `⚠️  ${label}: bounding-box largest dimension is Infinity — model hierarchy may be corrupt`
    );
  }
  if (largestDim < 1e-6 && largestDim !== 0) {
    console.warn(`⚠️  ${label}: bounding-box largest dimension is extremely small (${largestDim})`);
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

  // Enable shadows on every mesh
  model.traverse((child) => {
    if (child.isMesh) {
      child.castShadow = true;
      child.receiveShadow = true;
    }
  });

  return wrapper;
}

/**
 * Detailed inspection and verification for the loaded Earth GLB.
 * Also enforces correct SRGBColorSpace on the diffuse map as a safety net,
 * since the KHR_materials_pbrSpecularGlossiness extension resolves the texture
 * asynchronously and this function runs after all promises are settled.
 */
function inspectAndVerifyEarth(earthGltf) {
  const root = earthGltf.scene;
  const stats = collectMeshStats(root);

  let meshCount = 0;
  let hasBaseColorTexture = false;
  let textureDimensions = 'N/A';
  let textureColorSpace = 'N/A';
  let hasUVs = false;
  let hasNormals = false;
  const uniqueMaterials = new Set();
  const uniqueTextures = new Set();

  if (DEBUG_MODE) {
    console.log('--- Earth GLB loaded successfully ---');
    console.log('Scene children:', root.children.length);
  }

  root.traverse((child) => {
    if (!child.isMesh) return;

    meshCount++;

    if (DEBUG_MODE) {
      console.log('Earth mesh:', child.name || child.uuid);
    }

    // Geometry attributes
    const geo = child.geometry;
    if (geo && geo.attributes) {
      if (geo.attributes.uv) hasUVs = true;
      if (geo.attributes.normal) hasNormals = true;
      if (DEBUG_MODE) {
        console.log(
          `  UVs: ${geo.attributes.uv ? geo.attributes.uv.count : 'none'}`,
          `  Normals: ${geo.attributes.normal ? geo.attributes.normal.count : 'none'}`
        );
      }
    }

    const mat = child.material;
    if (!mat) return;
    uniqueMaterials.add(mat);

    if (DEBUG_MODE) {
      console.log('  Material type:', mat.type);
      console.log('  mat.map:', mat.map ? `present (colorSpace=${mat.map.colorSpace})` : 'NULL');
      console.log('  mat.color:', mat.color ? `#${mat.color.getHexString()}` : null);
      console.log('  mat.emissive:', mat.emissive ? `#${mat.emissive.getHexString()}` : null);
      console.log('  mat.emissiveIntensity:', mat.emissiveIntensity);
      console.log('  mat.roughness:', mat.roughness, '  mat.metalness:', mat.metalness);
    }

    if (mat.map) {
      uniqueTextures.add(mat.map);
      hasBaseColorTexture = true;

      // Authoritative color-space stamp: diffuse/albedo maps must be sRGB.
      // GLTFSpecGlossExtension already stamps this, but we enforce it here
      // as a belt-and-suspenders after all async texture work is settled.
      mat.map.colorSpace = THREE.SRGBColorSpace;
      mat.map.needsUpdate = true;
      textureColorSpace = mat.map.colorSpace;

      const img = mat.map.image || (mat.map.source && mat.map.source.data);
      if (img) textureDimensions = `${img.width}x${img.height}`;

      mat.needsUpdate = true;

      if (DEBUG_MODE) {
        console.log(`  Texture colorSpace set to: ${textureColorSpace}`);
        console.log(`  Texture dimensions: ${textureDimensions}`);
      }
    } else if (DEBUG_MODE) {
      console.warn('  ⚠️  mat.map is NULL — diffuse texture not loaded');
    }
  });

  if (DEBUG_MODE) {
    console.log('========================================');
    console.log('EARTH GLB CHECKLIST:');
    console.log(`  GLB loads?          YES`);
    console.log(`  Mesh count:         ${meshCount}`);
    console.log(`  Triangle count:     ${stats.triangleCount.toLocaleString()}`);
    console.log(`  UVs exist?          ${hasUVs ? 'YES' : 'NO'}`);
    console.log(`  Normals exist?      ${hasNormals ? 'YES' : 'NO'}`);
    console.log(`  Material count:     ${uniqueMaterials.size}`);
    console.log(`  Base-color texture? ${hasBaseColorTexture ? 'YES' : 'NO'}`);
    console.log(`  Texture dimensions: ${textureDimensions}`);
    console.log(`  Texture colorSpace: ${textureColorSpace}`);
    console.log('========================================');
  }
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

  // Register the plugin for KHR_materials_pbrSpecularGlossiness so Earth's embedded textures load properly
  loader.register((parser) => new GLTFSpecGlossExtension(parser));

  /**
   * Promise-based GLB loader with clear success/error logging.
   */
  function loadGLB(url, label) {
    console.log(`⏳ Loading ${label} from ${url} …`);

    return new Promise((resolve, reject) => {
      loader.load(
        url,
        (gltf) => {
          console.log(`✅ ${label} loaded successfully`);
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
  // Load all three GLBs in parallel using relative base URL
  // ------------------------------------------------------------------
  const baseUrl =
    (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.BASE_URL) || './';
  const cleanBase = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;

  const [earthGltf, sat1Gltf, sat2Gltf] = await Promise.all([
    loadGLB(`${cleanBase}assets/earth.glb`, 'Earth'),
    loadGLB(`${cleanBase}assets/satellite.glb`, 'Satellite 1'),
    loadGLB(`${cleanBase}assets/satellite2.glb`, 'Satellite 2')
  ]);

  // ------------------------------------------------------------------
  // Inspect and verify Earth GLB hierarchy, materials, textures & UVs
  // ------------------------------------------------------------------
  inspectAndVerifyEarth(earthGltf);

  // ------------------------------------------------------------------
  // Earth — normalize to diameter = EARTH_RADIUS * 2 (radius = 10)
  // ------------------------------------------------------------------
  const earth = normalizeModel(earthGltf.scene, EARTH_RADIUS * 2, 'Earth');
  earth.position.set(0, 0, 0);
  earth.traverse((child) => {
    if (child.isMesh) {
      child.receiveShadow = true;
    }
  });
  scene.add(earth);

  // ------------------------------------------------------------------
  // Satellite 1 — normalize to diameter = SATELLITE_SIZE * 2
  // Disable castShadow on all satellite meshes so no shadow is cast on Earth
  // ------------------------------------------------------------------
  const satellite1 = normalizeModel(sat1Gltf.scene, SATELLITE_SIZE * 2, 'Satellite 1');
  satellite1.traverse((child) => {
    if (child.isMesh) {
      child.castShadow = false;
    }
  });
  scene.add(satellite1);

  // ------------------------------------------------------------------
  // Satellite 2 — loaded from a separate file, normalized independently
  // Disable castShadow on all satellite meshes so no shadow is cast on Earth
  // ------------------------------------------------------------------
  const satellite2 = normalizeModel(sat2Gltf.scene, SATELLITE_SIZE * 2, 'Satellite 2');
  satellite2.traverse((child) => {
    if (child.isMesh) {
      child.castShadow = false;
    }
  });
  scene.add(satellite2);

  // ------------------------------------------------------------------
  console.log('🚀 All assets loaded and normalized');

  return { earth, satellite1, satellite2 };
}
