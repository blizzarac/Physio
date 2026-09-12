import { useEffect, useMemo } from "react";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import type { ThreeEvent } from "@react-three/fiber";
import type { StructureSummary } from "../api";
import { api } from "../api";
import { TISSUE, createAnatomyMaterial, principalAxis } from "../three/anatomyMaterial";

export type Tint = "selected" | "hovered" | "referral" | "antagonist" | "synergist" | "exercise" | "attachment" | null;

// Highlight colour, how far the base colour is pulled toward it, and rim-glow strength.
const TINT: Record<NonNullable<Tint>, { color: string; mix: number; glow: number }> = {
  selected: { color: "#ffcf4a", mix: 0.16, glow: 1.1 },
  hovered: { color: "#ffe7a3", mix: 0.06, glow: 0.5 },
  referral: { color: "#ff2e1f", mix: 0.28, glow: 1.0 },
  antagonist: { color: "#3f8cff", mix: 0.18, glow: 0.8 },
  synergist: { color: "#3ddc74", mix: 0.18, glow: 0.8 },
  exercise: { color: "#ff8c42", mix: 0.18, glow: 0.8 },
  attachment: { color: "#c77dff", mix: 0.1, glow: 0.6 },
};

interface Props {
  structure: StructureSummary;
  tint: Tint;
  xray: boolean;
  dimmed: boolean;
  onSelect: (id: string) => void;
  onFocus: (id: string) => void;
  onHover: (id: string | null) => void;
}

// One draw call per structure; each GLB comes from the bundle (one file per FMA ID) so the
// viewer can load lazily by layer. Picking is raycast-based via r3f pointer events; GPU ID
// picking (design doc §8) can replace it once the full-body mesh count makes raycasting slow.
export function StructureMesh({ structure, tint, xray, dimmed, onSelect, onFocus, onHover }: Props) {
  const gltf = useGLTF(api.meshUrl(structure.mesh_url!));
  const geometry = useMemo(() => {
    const geoms: THREE.BufferGeometry[] = [];
    gltf.scene.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) geoms.push((o as THREE.Mesh).geometry);
    });
    const g = geoms[0];
    // Defensive: a GLB without normals would render black (NaN lighting).
    if (g && !g.attributes.normal) g.computeVertexNormals();
    return g;
  }, [gltf]);

  const material = useMemo(() => {
    const m = createAnatomyMaterial(structure.type);
    if (geometry) {
      const { axis, perp } = principalAxis(geometry);
      m.anatomy.uAxis.value.copy(axis);
      m.anatomy.uPerp.value.copy(perp);
    }
    return m;
  }, [structure.type, geometry]);

  useEffect(() => () => material.dispose(), [material]);

  useEffect(() => {
    const u = material.anatomy;
    if (tint) {
      const t = TINT[tint];
      u.uTint.value.set(t.color);
      u.uTintMix.value = t.mix;
      u.uGlow.value = t.glow;
    } else {
      u.uTintMix.value = 0;
      u.uGlow.value = 0;
    }
  }, [tint, material]);

  useEffect(() => {
    const seeThrough = xray && structure.type === "muscle" && !tint;
    const base = TISSUE[structure.type]?.opacity ?? 1;
    const opacity = dimmed ? 0.1 : seeThrough ? 0.35 : base;
    material.transparent = opacity < 1;
    material.opacity = opacity;
    material.depthWrite = opacity >= 1;
    material.needsUpdate = true;
  }, [xray, dimmed, tint, material, structure.type]);

  if (!geometry) return null;
  return (
    <mesh
      geometry={geometry}
      material={material}
      castShadow
      receiveShadow
      onClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation();
        onSelect(structure.id);
      }}
      onDoubleClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation();
        onFocus(structure.id);
      }}
      onPointerOver={(e: ThreeEvent<PointerEvent>) => {
        e.stopPropagation();
        onHover(structure.id);
      }}
      onPointerOut={() => onHover(null)}
    />
  );
}
