import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";
import { api, type StructureSummary } from "../api";
import { useStore } from "../store";
import { StructureMesh, type Tint } from "./StructureMesh";
import { SceneSetup, type SceneBounds } from "../three/Scene";

function boundsOf(structures: StructureSummary[]): SceneBounds {
  const pts = structures.map((s) => s.centroid).filter((c): c is [number, number, number] => !!c);
  if (pts.length === 0) return { center: new THREE.Vector3(0, 0, 0), radius: 1, minY: -1 };
  const box = new THREE.Box3();
  for (const p of pts) box.expandByPoint(new THREE.Vector3(...p));
  const center = box.getCenter(new THREE.Vector3());
  // centroids underestimate the extent; pad by a share of the largest span
  const size = box.getSize(new THREE.Vector3());
  const radius = Math.max(size.x, size.y, size.z) * 0.6 + 0.15;
  return { center, radius, minY: box.min.y - Math.max(size.y * 0.25, 0.1) };
}

function tintFor(id: string, h: ReturnType<typeof useStore.getState>["highlights"], hovered: string | null): Tint {
  if (h.selected === id) return "selected";
  if (hovered === id) return "hovered";
  if (h.referral.has(id)) return "referral";
  if (h.antagonists.has(id)) return "antagonist";
  if (h.synergists.has(id)) return "synergist";
  if (h.exercise.has(id)) return "exercise";
  if (h.attachments.has(id)) return "attachment";
  return null;
}

// Smoothly re-targets the orbit controls when the store's cameraTarget changes (search jump).
function CameraRig({ controls }: { controls: React.RefObject<OrbitControlsImpl> }) {
  const target = useStore((s) => s.cameraTarget);
  const flyTo = useStore((s) => s.flyTo);
  const { camera } = useThree();
  const goal = useRef<THREE.Vector3 | null>(null);
  useEffect(() => {
    goal.current = target ? new THREE.Vector3(...target) : null;
  }, [target]);
  useFrame(() => {
    const c = controls.current;
    if (!goal.current || !c) return;
    c.target.lerp(goal.current, 0.12);
    const desired = goal.current.clone().add(new THREE.Vector3(0, 0.15, 0.7));
    camera.position.lerp(desired, 0.08);
    c.update();
    if (c.target.distanceTo(goal.current) < 0.002) {
      goal.current = null;
      flyTo(null);
    }
  });
  return null;
}

export function Viewer() {
  const [structures, setStructures] = useState<StructureSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const layers = useStore((s) => s.layers);
  const highlights = useStore((s) => s.highlights);
  const hovered = useStore((s) => s.hoveredId);
  const select = useStore((s) => s.select);
  const hover = useStore((s) => s.hover);
  const xray = useStore((s) => s.xray);
  const effects = useStore((s) => s.effects);
  const controls = useRef<OrbitControlsImpl>(null);

  useEffect(() => {
    api.structures(true).then(setStructures).catch((e) => setError(String(e)));
  }, []);

  const visible = structures.filter((s) => (layers as Record<string, boolean>)[s.type] ?? true);
  const bounds = useMemo(() => boundsOf(structures), [structures]);
  const hoveredName = structures.find((s) => s.id === hovered)?.name;

  return (
    <div className="relative h-full w-full">
      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.05 }}
        camera={{ position: [0, 0.2, 2.2], fov: 40, near: 0.01, far: 50 }}
        onPointerMissed={() => select(null)}
      >
        <color attach="background" args={["#141416"]} />
        <fog attach="fog" args={["#141416", bounds.radius * 6, bounds.radius * 14]} />
        <SceneSetup bounds={bounds} effects={effects} />
        <Suspense fallback={<Html center className="text-neutral-400">loading meshes…</Html>}>
          {visible.map((s) => (
            <StructureMesh
              key={s.id}
              structure={s}
              tint={tintFor(s.id, highlights, hovered)}
              xray={xray}
              onSelect={select}
              onHover={hover}
            />
          ))}
        </Suspense>
        <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={0.1} />
        <CameraRig controls={controls} />
      </Canvas>
      {hoveredName && (
        <div className="pointer-events-none absolute left-3 top-3 rounded bg-black/70 px-2 py-1 text-sm">
          {hoveredName}
        </div>
      )}
      {error && (
        <div className="absolute inset-x-0 top-0 bg-red-900/80 p-2 text-sm">
          Could not load structures: {error}. Is the API running and the bundle built?
        </div>
      )}
      {!error && structures.length === 0 && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-neutral-500">
          No meshes in the bundle yet.
        </div>
      )}
    </div>
  );
}
