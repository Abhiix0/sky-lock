import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
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
 */
function inspectAndVerifyEarth(earthGltf) {
  const root = earthGltf.scene;
  const stats = collectMeshStats(root);

  let meshCount = 0;
  let materialCount = 0;
  let textureCount = 0;
  const uniqueMaterials = new Set();
  const uniqueTextures = new Set();

  console.log('--- Earth GLB loaded successfully ---');
  console.log('Scene children:', root.children.length);

  // Traverse the entire hierarchy as instructed
  root.traverse((child) => {
    if (child.isMesh) {
      meshCount++;
      console.log('Earth mesh:', child);
      console.log('Geometry:', child.geometry);
      console.log('Material:', child.material);

      if (child.material) {
        uniqueMaterials.add(child.material);
        if (child.material.map) {
          uniqueTextures.add(child.material.map);
        }
      }
    }
  });

  materialCount = uniqueMaterials.size;
  textureCount = uniqueTextures.size;

  console.log(`Mesh count: ${meshCount}`);
  console.log(`Material count: ${materialCount}`);
  console.log(`Texture count: ${textureCount}`);
  console.log(`Triangle count: ${stats.triangleCount.toLocaleString()}`);

  // Inspect materials and enforce proper color space on color/albedo textures
  let hasBaseColorTexture = false;
  let textureDimensions = 'N/A';
  let textureColorSpace = 'N/A';
  let hasUVs = false;
  let hasNormals = false;

  root.traverse((child) => {
    if (child.isMesh) {
      const geo = child.geometry;
      if (geo && geo.attributes) {
        if (geo.attributes.uv) {
          hasUVs = true;
          console.log(`Geometry UVs: count=${geo.attributes.uv.count}, itemSize=${geo.attributes.uv.itemSize}`);
        }
        if (geo.attributes.normal) {
          hasNormals = true;
          console.log(`Geometry Normals: count=${geo.attributes.normal.count}, itemSize=${geo.attributes.normal.itemSize}`);
        }
      }

      const mat = child.material;
      if (mat) {
        console.log('--- Earth Mesh Material Inspection ---', {
          'material.type': mat.type,
          'material.map': mat.map ? mat.map.name || 'Texture present' : null,
          'material.color': mat.color ? `#${mat.color.getHexString()}` : null,
          'material.normalMap': mat.normalMap ? 'Present' : null,
          'material.roughnessMap': mat.roughnessMap ? 'Present' : null,
          'material.metalnessMap': mat.metalnessMap ? 'Present' : null,
          'material.emissiveMap': mat.emissiveMap ? 'Present' : null,
          'material.transparent': mat.transparent,
          'material.opacity': mat.opacity,
          'material.roughness': mat.roughness,
          'material.metalness': mat.metalness
        });

        // Step 4: Fix texture color space correctly for color/albedo map
        if (mat.map) {
          hasBaseColorTexture = true;
          mat.map.colorSpace = THREE.SRGBColorSpace;
          mat.map.needsUpdate = true;
          textureColorSpace = mat.map.colorSpace;

          if (mat.map.image) {
            textureDimensions = `${mat.map.image.width}x${mat.map.image.height}`;
          } else if (mat.map.source && mat.map.source.data) {
            textureDimensions = `${mat.map.source.data.width}x${mat.map.source.data.height}`;
          }

          mat.needsUpdate = true;
        }
      }
    }
  });

  // Critical Debugging Checklist
  console.log('========================================');
  console.log('CRITICAL DEBUGGING CHECKLIST:');
  console.log('GLB loads?          YES');
  console.log(`Geometry loads?     ${meshCount > 0 ? 'YES' : 'NO'}`);
  console.log(`UVs exist?          ${hasUVs ? 'YES' : 'NO'}`);
  console.log(`Normals exist?      ${hasNormals ? 'YES' : 'NO'}`);
  console.log(`Material exists?    ${materialCount > 0 ? 'YES' : 'NO'}`);
  console.log(`Base-color texture? ${hasBaseColorTexture ? 'YES' : 'NO'}`);
  console.log(`Texture dimensions: ${textureDimensions}`);
  console.log(`Texture color space: ${textureColorSpace}`);
  console.log('========================================');
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
  // Load all three GLBs in parallel
  // ------------------------------------------------------------------
  const [earthGltf, sat1Gltf, sat2Gltf] = await Promise.all([
    loadGLB('/assets/earth.glb', 'Earth'),
    loadGLB('/assets/satellite.glb', 'Satellite 1'),
    loadGLB('/assets/satellite2.glb', 'Satellite 2'),
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
