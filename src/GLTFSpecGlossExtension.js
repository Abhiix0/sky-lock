import { Color, MeshStandardMaterial, SRGBColorSpace } from 'three';

/**
 * GLTFLoader plugin for the deprecated KHR_materials_pbrSpecularGlossiness
 * extension.  Three.js dropped built-in support around r152; this shim
 * converts spec-gloss data to MeshStandardMaterial so older Earth GLBs
 * authored with that workflow still render correctly.
 *
 * Spec: https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Archived/KHR_materials_pbrSpecularGlossiness
 *
 * Usage:
 *   loader.register((parser) => new GLTFSpecGlossExtension(parser));
 */
export class GLTFSpecGlossExtension {
  constructor(parser) {
    this.parser = parser;
    this.name = 'KHR_materials_pbrSpecularGlossiness';
  }

  /**
   * Return MeshStandardMaterial for any material that uses this extension.
   */
  getMaterialType(materialIndex) {
    const materialDef = this.parser.json.materials[materialIndex];
    if (!materialDef.extensions || !materialDef.extensions[this.name]) return null;
    return MeshStandardMaterial;
  }

  /**
   * Convert spec-gloss parameters to metallic-roughness equivalents.
   */
  extendMaterialParams(materialIndex, materialParams) {
    const parser = this.parser;
    const materialDef = parser.json.materials[materialIndex];

    if (!materialDef.extensions || !materialDef.extensions[this.name]) {
      return Promise.resolve();
    }

    const ext = materialDef.extensions[this.name];
    const pending = [];

    // ---- Diffuse color ----
    if (ext.diffuseFactor) {
      materialParams.color = new Color().setRGB(
        ext.diffuseFactor[0],
        ext.diffuseFactor[1],
        ext.diffuseFactor[2],
        SRGBColorSpace
      );
      materialParams.opacity = ext.diffuseFactor[3] !== undefined ? ext.diffuseFactor[3] : 1.0;
    }

    // ---- Diffuse texture → map ----
    if (ext.diffuseTexture !== undefined) {
      pending.push(
        parser.assignTexture(materialParams, 'map', ext.diffuseTexture, SRGBColorSpace)
      );
    }

    // ---- Glossiness → Roughness ----
    const glossiness = ext.glossinessFactor !== undefined ? ext.glossinessFactor : 1.0;
    materialParams.roughness = 1.0 - glossiness;

    // ---- Specular → approximate metalness ----
    // In the spec-gloss workflow, dielectrics have low specular (~0.04) and
    // metals have high specular matching the diffuse color.  A simple
    // luminance-based heuristic maps this onto metalness.
    if (ext.specularFactor) {
      const r = ext.specularFactor[0];
      const g = ext.specularFactor[1];
      const b = ext.specularFactor[2];
      const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      materialParams.metalness = Math.min(luminance, 1.0);
    } else {
      materialParams.metalness = 0.0;
    }

    // ---- Specular-glossiness texture (optional) ----
    // We don't have a clean way to split this into separate metallicRoughness
    // channels, so we simply ignore it.  The diffuse texture carries the
    // visual information that matters most.

    console.log(
      `[SpecGloss] Material ${materialIndex}: diffuse=(${ext.diffuseFactor?.join(',')}), ` +
      `glossiness=${glossiness}, roughness=${materialParams.roughness.toFixed(2)}, ` +
      `metalness=${materialParams.metalness?.toFixed(2)}, ` +
      `hasDiffuseTex=${ext.diffuseTexture !== undefined}`
    );

    return Promise.all(pending);
  }
}
