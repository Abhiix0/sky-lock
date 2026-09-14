import { Color, MeshStandardMaterial, SRGBColorSpace, LinearSRGBColorSpace } from 'three';

/**
 * GLTFLoader plugin for the KHR_materials_pbrSpecularGlossiness extension.
 * Converts legacy specular-glossiness material definitions into MeshStandardMaterial
 * so that Sketchfab and other glTF 2.0 assets authored with this extension
 * (such as earth.glb) retain their diffuse color/textures and render properly.
 *
 * Spec: https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Archived/KHR_materials_pbrSpecularGlossiness
 */
export class GLTFSpecGlossExtension {
  constructor(parser) {
    this.parser = parser;
    this.name = 'KHR_materials_pbrSpecularGlossiness';
  }

  /**
   * Instructs GLTFLoader to instantiate a MeshStandardMaterial for this material.
   */
  getMaterialType(materialIndex) {
    const materialDef = this.parser.json.materials[materialIndex];
    if (!materialDef || !materialDef.extensions || !materialDef.extensions[this.name]) {
      return null;
    }
    return MeshStandardMaterial;
  }

  /**
   * Asynchronously assigns textures and sets parameters on materialParams.
   */
  extendMaterialParams(materialIndex, materialParams) {
    const parser = this.parser;
    const materialDef = parser.json.materials[materialIndex];

    if (!materialDef || !materialDef.extensions || !materialDef.extensions[this.name]) {
      return Promise.resolve();
    }

    const ext = materialDef.extensions[this.name];
    const pending = [];

    // 1. Diffuse Factor (Base Color) - Linear sRGB in glTF specification
    materialParams.color = new Color(1, 1, 1);
    materialParams.opacity = 1.0;

    if (Array.isArray(ext.diffuseFactor)) {
      materialParams.color.setRGB(
        ext.diffuseFactor[0],
        ext.diffuseFactor[1],
        ext.diffuseFactor[2],
        LinearSRGBColorSpace
      );
      if (ext.diffuseFactor[3] !== undefined) {
        materialParams.opacity = ext.diffuseFactor[3];
      }
    }

    // 2. Diffuse Texture -> MeshStandardMaterial.map (sRGB color space)
    if (ext.diffuseTexture !== undefined) {
      pending.push(
        parser.assignTexture(materialParams, 'map', ext.diffuseTexture, SRGBColorSpace)
      );
    }

    // 3. Glossiness -> Roughness conversion: roughness = 1 - glossiness
    const glossiness = ext.glossinessFactor !== undefined ? ext.glossinessFactor : 0.0;
    materialParams.roughness = Math.max(0.1, Math.min(1.0, 1.0 - glossiness));

    // 4. Specular Factor -> Metalness approximation:
    // Non-metals have low specular (~0.04), metals have higher specular.
    if (Array.isArray(ext.specularFactor)) {
      const r = ext.specularFactor[0];
      const g = ext.specularFactor[1];
      const b = ext.specularFactor[2];
      const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      // In earth.glb specular is [0,0,0], giving metalness = 0.0
      materialParams.metalness = Math.min(luminance, 1.0);
    } else {
      materialParams.metalness = 0.0;
    }

    console.log(`[GLTFSpecGlossExtension] Successfully parsed material "${materialDef.name || materialIndex}":`, {
      diffuseFactor: ext.diffuseFactor,
      hasDiffuseTexture: ext.diffuseTexture !== undefined,
      roughness: materialParams.roughness,
      metalness: materialParams.metalness
    });

    return Promise.all(pending);
  }
}
