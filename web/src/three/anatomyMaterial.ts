import * as THREE from "three";
import type { StructureType } from "../api";

// Physically based tissue materials with a small shader extension:
//  - procedural fibre striations along each mesh's principal axis (muscles, tendons)
//  - low-frequency mottling so large surfaces do not look like flat plastic
//  - highlight = base colour tinted toward uTint plus a Fresnel rim glow, so a selected
//    or related structure stays shaded instead of turning into a flat colour.
// Everything is generated in the shader from world position; BodyParts3D meshes carry no
// UVs and no textures are fetched at runtime.

export interface TissueLook {
  color: string;
  roughness: number;
  metalness: number;
  clearcoat: number;
  clearcoatRoughness: number;
  sheen: number;
  sheenColor: string;
  sheenRoughness: number;
  fiber: number;      // striation strength 0..1
  fiberScale: number; // stripes per metre
  mottle: number;     // low-frequency colour variation 0..1
  opacity: number;
}

export const TISSUE: Record<StructureType, TissueLook> = {
  muscle: {
    color: "#7d2a25", roughness: 0.48, metalness: 0, clearcoat: 0.45, clearcoatRoughness: 0.35,
    sheen: 0.35, sheenColor: "#b8433a", sheenRoughness: 0.6, fiber: 0.5, fiberScale: 240, mottle: 0.18, opacity: 1,
  },
  tendon: {
    color: "#e9e3d2", roughness: 0.42, metalness: 0, clearcoat: 0.3, clearcoatRoughness: 0.3,
    sheen: 0.5, sheenColor: "#ffffff", sheenRoughness: 0.4, fiber: 0.35, fiberScale: 420, mottle: 0.08, opacity: 1,
  },
  ligament: {
    color: "#dfd7c3", roughness: 0.5, metalness: 0, clearcoat: 0.2, clearcoatRoughness: 0.4,
    sheen: 0.4, sheenColor: "#ffffff", sheenRoughness: 0.5, fiber: 0.3, fiberScale: 380, mottle: 0.1, opacity: 1,
  },
  bone: {
    color: "#e6dfcb", roughness: 0.68, metalness: 0, clearcoat: 0.05, clearcoatRoughness: 0.6,
    sheen: 0.15, sheenColor: "#fff6e0", sheenRoughness: 0.8, fiber: 0, fiberScale: 0, mottle: 0.22, opacity: 1,
  },
  joint: {
    color: "#cfd9df", roughness: 0.25, metalness: 0, clearcoat: 0.6, clearcoatRoughness: 0.2,
    sheen: 0.2, sheenColor: "#ffffff", sheenRoughness: 0.3, fiber: 0, fiberScale: 0, mottle: 0.08, opacity: 0.85,
  },
  fascia: {
    color: "#efe7d6", roughness: 0.35, metalness: 0, clearcoat: 0.5, clearcoatRoughness: 0.25,
    sheen: 0.6, sheenColor: "#ffffff", sheenRoughness: 0.3, fiber: 0.15, fiberScale: 300, mottle: 0.1, opacity: 0.75,
  },
  region: {
    color: "#b9a690", roughness: 0.7, metalness: 0, clearcoat: 0, clearcoatRoughness: 1,
    sheen: 0, sheenColor: "#000000", sheenRoughness: 1, fiber: 0, fiberScale: 0, mottle: 0.1, opacity: 1,
  },
};

export interface AnatomyUniforms {
  uTint: { value: THREE.Color };
  uTintMix: { value: number };
  uGlow: { value: number };
  uAxis: { value: THREE.Vector3 };
  uPerp: { value: THREE.Vector3 };
  uFiber: { value: number };
  uFiberScale: { value: number };
  uMottle: { value: number };
  uSeed: { value: number };
}

export type AnatomyMaterial = THREE.MeshPhysicalMaterial & { anatomy: AnatomyUniforms };

const NOISE_GLSL = /* glsl */ `
  float anatHash(vec3 p) {
    p = fract(p * 0.3183099 + vec3(0.1, 0.7, 0.4));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
  }
  float anatNoise(vec3 x) {
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
      mix(mix(anatHash(i + vec3(0, 0, 0)), anatHash(i + vec3(1, 0, 0)), f.x),
          mix(anatHash(i + vec3(0, 1, 0)), anatHash(i + vec3(1, 1, 0)), f.x), f.y),
      mix(mix(anatHash(i + vec3(0, 0, 1)), anatHash(i + vec3(1, 0, 1)), f.x),
          mix(anatHash(i + vec3(0, 1, 1)), anatHash(i + vec3(1, 1, 1)), f.x), f.y),
      f.z);
  }
  float anatFbm(vec3 p) {
    return 0.5 * anatNoise(p) + 0.25 * anatNoise(p * 2.03) + 0.125 * anatNoise(p * 4.11);
  }
`;

export function createAnatomyMaterial(type: StructureType): AnatomyMaterial {
  const look = TISSUE[type] ?? TISSUE.region;
  const mat = new THREE.MeshPhysicalMaterial({
    color: look.color,
    roughness: look.roughness,
    metalness: look.metalness,
    clearcoat: look.clearcoat,
    clearcoatRoughness: look.clearcoatRoughness,
    sheen: look.sheen,
    sheenColor: new THREE.Color(look.sheenColor),
    sheenRoughness: look.sheenRoughness,
    transparent: look.opacity < 1,
    opacity: look.opacity,
    envMapIntensity: 0.9,
  }) as AnatomyMaterial;

  const uniforms: AnatomyUniforms = {
    uTint: { value: new THREE.Color("#ffffff") },
    uTintMix: { value: 0 },
    uGlow: { value: 0 },
    uAxis: { value: new THREE.Vector3(0, 1, 0) },
    uPerp: { value: new THREE.Vector3(1, 0, 0) },
    uFiber: { value: look.fiber },
    uFiberScale: { value: look.fiberScale },
    uMottle: { value: look.mottle },
    uSeed: { value: Math.random() * 100 },
  };
  mat.anatomy = uniforms;

  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vAnatPos;")
      .replace(
        "#include <worldpos_vertex>",
        "#include <worldpos_vertex>\nvAnatPos = (modelMatrix * vec4(transformed, 1.0)).xyz;",
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        varying vec3 vAnatPos;
        uniform vec3 uTint; uniform float uTintMix; uniform float uGlow;
        uniform vec3 uAxis; uniform vec3 uPerp;
        uniform float uFiber; uniform float uFiberScale; uniform float uMottle; uniform float uSeed;
        ${NOISE_GLSL}`,
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        {
          vec3 p = vAnatPos + vec3(uSeed);
          // low-frequency mottling: slightly darker / redder patches
          float m = anatFbm(p * 35.0) - 0.5;
          diffuseColor.rgb *= 1.0 + uMottle * 1.6 * m;
          // fibre striations: stripes perpendicular to the principal axis, warped by noise
          if (uFiber > 0.0) {
            float along = dot(p, uAxis);
            float across = dot(p, uPerp) + 0.0025 * (anatFbm(p * 40.0) - 0.5);
            float stripe = 0.5 + 0.5 * sin(across * uFiberScale * 6.2831853 + 1.2 * anatNoise(vec3(along * 18.0, across * 3.0, uSeed)));
            float bundles = 0.5 + 0.5 * sin(across * uFiberScale * 0.35 + 1.5 * anatNoise(vec3(along * 6.0, across * 2.0, uSeed)));
            float aa = 1.0 - smoothstep(0.6, 2.5, fwidth(across * uFiberScale));
            float f = mix(0.5, stripe * 0.55 + bundles * 0.45, aa);
            diffuseColor.rgb *= 1.0 + uFiber * 0.9 * (f - 0.5);
          }
          diffuseColor.rgb = mix(diffuseColor.rgb, uTint, uTintMix);
        }`,
      )
      .replace(
        "#include <emissivemap_fragment>",
        `#include <emissivemap_fragment>
        {
          // rim-only glow: the tissue keeps its shading, the silhouette carries the colour
          float fresnel = pow(1.0 - saturate(dot(normalize(vViewPosition), normal)), 2.6);
          totalEmissiveRadiance += uTint * uGlow * (0.03 + 0.97 * fresnel);
        }`,
      );
  };
  // Distinct program per look so the injected uniforms are never shared across types.
  mat.customProgramCacheKey = () => `anatomy-${type}`;
  return mat;
}

/** Principal axis of a geometry (largest eigenvector of the vertex covariance). */
export function principalAxis(geometry: THREE.BufferGeometry): { axis: THREE.Vector3; perp: THREE.Vector3 } {
  const pos = geometry.attributes.position as THREE.BufferAttribute;
  const n = pos.count;
  const step = Math.max(1, Math.floor(n / 4000));
  let cx = 0, cy = 0, cz = 0, m = 0;
  for (let i = 0; i < n; i += step) { cx += pos.getX(i); cy += pos.getY(i); cz += pos.getZ(i); m++; }
  cx /= m; cy /= m; cz /= m;
  let xx = 0, xy = 0, xz = 0, yy = 0, yz = 0, zz = 0;
  for (let i = 0; i < n; i += step) {
    const x = pos.getX(i) - cx, y = pos.getY(i) - cy, z = pos.getZ(i) - cz;
    xx += x * x; xy += x * y; xz += x * z; yy += y * y; yz += y * z; zz += z * z;
  }
  const c = new THREE.Matrix3().set(xx, xy, xz, xy, yy, yz, xz, yz, zz);
  let v = new THREE.Vector3(1, 1, 1).normalize();
  for (let i = 0; i < 24; i++) v = v.applyMatrix3(c).normalize();
  const axis = v;
  const helper = Math.abs(axis.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
  const perp = new THREE.Vector3().crossVectors(axis, helper).normalize();
  return { axis, perp };
}
