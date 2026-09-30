import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { readFile } from 'fs/promises';
import { GLTFSpecGlossExtension } from '../src/GLTFSpecGlossExtension.js';

console.log('=== Debugging earth.glb ===\n');

// Load the GLB file as binary
const glbPath = './public/assets/earth.glb';
console.log(`Loading ${glbPath}...`);

try {
  const buffer = await readFile(glbPath);
  console.log(`✅ File loaded: ${buffer.length} bytes`);
  
  // Parse with GLTFLoader and register our extension
  const loader = new GLTFLoader();
  loader.register((parser) => new GLTFSpecGlossExtension(parser));
  console.log('✅ GLTFSpecGlossExtension registered\n');
  
  loader.parse(
    buffer.buffer,
    '',
    (gltf) => {
      console.log('\n✅ GLTF parsed successfully\n');
      
      // Check the raw JSON
      const json = gltf.parser.json;
      console.log('Materials in GLB:', json.materials?.length || 0);
      
      if (json.materials) {
        json.materials.forEach((mat, idx) => {
          console.log(`\n--- Material ${idx}: ${mat.name || 'unnamed'} ---`);
          console.log('Extensions:', Object.keys(mat.extensions || {}));
          
          if (mat.extensions && mat.extensions.KHR_materials_pbrSpecularGlossiness) {
            const ext = mat.extensions.KHR_materials_pbrSpecularGlossiness;
            console.log('KHR_materials_pbrSpecularGlossiness found!');
            console.log('  diffuseFactor:', ext.diffuseFactor);
            console.log('  diffuseTexture:', ext.diffuseTexture);
            console.log('  specularFactor:', ext.specularFactor);
            console.log('  glossinessFactor:', ext.glossinessFactor);
          }
          
          if (mat.pbrMetallicRoughness) {
            console.log('pbrMetallicRoughness:');
            console.log('  baseColorFactor:', mat.pbrMetallicRoughness.baseColorFactor);
            console.log('  baseColorTexture:', mat.pbrMetallicRoughness.baseColorTexture);
          }
        });
      }
      
      console.log('\nTextures in GLB:', json.textures?.length || 0);
      if (json.textures) {
        json.textures.forEach((tex, idx) => {
          console.log(`Texture ${idx}:`, tex);
        });
      }
      
      console.log('\nImages in GLB:', json.images?.length || 0);
      if (json.images) {
        json.images.forEach((img, idx) => {
          console.log(`Image ${idx}:`, {
            name: img.name,
            mimeType: img.mimeType,
            bufferView: img.bufferView,
            uri: img.uri
          });
        });
      }
      
      // Check the loaded scene
      console.log('\n--- Loaded Scene ---');
      gltf.scene.traverse((obj) => {
        if (obj.isMesh) {
          console.log(`Mesh: ${obj.name}`);
          console.log(`  Material type: ${obj.material?.type}`);
          console.log(`  Has map: ${!!obj.material?.map}`);
          console.log(`  Color: ${obj.material?.color ? '#' + obj.material.color.getHexString() : 'N/A'}`);
        }
      });
    },
    (error) => {
      console.error('❌ Error parsing GLTF:', error);
    }
  );
} catch (err) {
  console.error('❌ Error loading file:', err);
}
