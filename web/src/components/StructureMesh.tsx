import { useEffect, useMemo } from "react";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import type { ThreeEvent } from "@react-three/fiber";
import type { StructureSummary } from "../api";
import { api } from "../api";

export type Tint = "selected" | "hovered" | "referral" | "antagonist" | "synergist" | "exercise" | "attachment" | null;

const BASE: Record<string, string> = {
  bone: "#e8e2d4",
  muscle: "#b5473f",
  tendon: "#e6dcc3",
  ligament: "#d8cfb8",
  joint: "#7fa7c9",
  fascia: "#cdb9a5",
  region: "#999999",
};

const TINT: Record<NonNullable<Tint>, string> = {
  selected: "#ffd23f",
  hovered: "#ffe89a",
  referral: "#ff3b1f",
  antagonist: "#3f8cff",
  synergist: "#40c463",
  exercise: "#ff8c42",
  attachment: "#c77dff",
};

interface Props {
  structure: StructureSummary;
  tint: Tint;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

// One draw call per structure; each GLB comes from the bundle (one file per FMA ID) so the
// viewer can load lazily by layer. Picking is raycast-based via r3f pointer events; GPU ID
// picking (design doc §8) can replace it once the full-body mesh count makes raycasting slow.
export function StructureMesh({ structure, tint, onSelect, onHover }: Props) {
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

  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: BASE[structure.type] ?? "#999",
        roughness: 0.75,
        metalness: 0.05,
        transparent: structure.type === "muscle",
        opacity: structure.type === "muscle" ? 0.92 : 1,
      }),
    [structure.type],
  );

  useEffect(() => {
    const color = tint ? TINT[tint] : BASE[structure.type] ?? "#999";
    material.color.set(color);
    material.emissive.set(tint ? color : "#000000");
    material.emissiveIntensity = tint === "selected" ? 0.45 : tint ? 0.25 : 0;
    material.needsUpdate = true;
  }, [tint, material, structure.type]);

  if (!geometry) return null;
  return (
    <mesh
      geometry={geometry}
      material={material}
      onClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation();
        onSelect(structure.id);
      }}
      onPointerOver={(e: ThreeEvent<PointerEvent>) => {
        e.stopPropagation();
        onHover(structure.id);
      }}
      onPointerOut={() => onHover(null)}
    />
  );
}
