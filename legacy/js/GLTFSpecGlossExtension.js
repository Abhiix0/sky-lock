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
   * This method is called by GLTFLoader to extend material parameters.
   */
  async extendMaterialParams(materialIndex, materialParams) {
    const parser = this.parser;
    const materialDef = parser.json.materials[materialIndex];

    if (!materialDef || !materialDef.extensions || !materialDef.extensions[this.name]) {
      return;
    }

    const ext = materialDef.extensions[this.name];
    const pending = [];

    // 1. Diffuse Factor (Base Color) — linear sRGB per glTF spec
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

    // 2. Diffuse Texture -> MeshStandardMaterial.map
    //    Pass SRGBColorSpace as the 4th argument so assignTexture stamps it on
    //    the texture object before returning — this is the authoritative place
    //    to set color space; doing it in a .then() risks a race with material
    //    finalisation in GLTFLoader r170+.
    if (ext.diffuseTexture !== undefined) {
      pending.push(
        parser
          .assignTexture(materialParams, 'map', ext.diffuseTexture, SRGBColorSpace)
          .then((texture) => {
            // Belt-and-suspenders: confirm color space and force GPU re-upload
            if (texture) {
              texture.colorSpace = SRGBColorSpace;
              texture.needsUpdate = true;
            }
          })
      );
    }

    // 3. Glossiness -> Roughness: roughness = 1 − glossiness
    //    Earth.glb has glossinessFactor = 0 → roughness = 1.0; keep matte but
    //    allow at least 0.4 so specular highlights are faintly visible.
    const glossiness = ext.glossinessFactor !== undefined ? ext.glossinessFactor : 0.0;
    materialParams.roughness = Math.max(0.4, Math.min(1.0, 1.0 - glossiness));

    // 4. Specular Factor -> Metalness approximation
    if (Array.isArray(ext.specularFactor)) {
      const r = ext.specularFactor[0];
      const g = ext.specularFactor[1];
      const b = ext.specularFactor[2];
      const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      materialParams.metalness = Math.min(luminance, 1.0);
    } else {
      materialParams.metalness = 0.0;
    }

    // Ensure the material respects the opacity value we set above
    if (materialParams.opacity < 1.0) {
      materialParams.transparent = true;
    }

    if (pending.length > 0) {
      await Promise.all(pending);
    }
  }
}
