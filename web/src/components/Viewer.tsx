import { Suspense, useEffect, useMemo, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { GizmoHelper, GizmoViewport, Html, OrbitControls } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";
import type { StructureSummary } from "../api";
import { unionBox, useStore, type ViewPreset } from "../store";
import { StructureMesh, type Tint } from "./StructureMesh";
import { SceneSetup, type SceneBounds } from "../three/Scene";
import { CameraRig } from "../three/CameraRig";
import { subtree } from "../nav/hierarchy";

function boundsOf(structures: StructureSummary[]): SceneBounds {
  const box = unionBox(structures, structures.map((s) => s.id));
  if (!box) return { center: new THREE.Vector3(0, 0, 0), radius: 1, minY: -1 };
  const b3 = new THREE.Box3(new THREE.Vector3(...box.min), new THREE.Vector3(...box.max));
  const center = b3.getCenter(new THREE.Vector3());
  const size = b3.getSize(new THREE.Vector3());
  return { center, radius: Math.max(size.x, size.y, size.z) * 0.6, minY: b3.min.y };
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

const PRESET_KEYS: Record<string, ViewPreset> = { "1": "anterior", "2": "posterior", "3": "left", "4": "right", "5": "superior" };

/** Meshed structures that make up `id`: itself, or every meshed descendant of a region. */
export function meshedMembers(id: string): string[] {
  const { structures, hierarchy } = useStore.getState();
  const ids = hierarchy ? subtree(hierarchy, id) : new Set([id]);
  return structures.filter((s) => ids.has(s.id) && s.bbox).map((s) => s.id);
}

/** Frame the camera on a structure or region (no-op when nothing of it has a mesh). */
export function frameStructure(id: string, preset?: ViewPreset) {
  const { structures, requestCamera } = useStore.getState();
  const box = unionBox(structures, meshedMembers(id));
  if (box) requestCamera({ kind: "frame", box, preset });
}

export function Viewer() {
  const structures = useStore((s) => s.structures);
  const error = useStore((s) => s.structuresError);
  const hierarchy = useStore((s) => s.hierarchy);
  const layers = useStore((s) => s.layers);
  const highlights = useStore((s) => s.highlights);
  const hovered = useStore((s) => s.hoveredId);
  const selectedId = useStore((s) => s.selectedId);
  const viewMode = useStore((s) => s.viewMode);
  const regionFilter = useStore((s) => s.regionFilter);
  const select = useStore((s) => s.select);
  const hover = useStore((s) => s.hover);
  const requestCamera = useStore((s) => s.requestCamera);
  const xray = useStore((s) => s.xray);
  const effects = useStore((s) => s.effects);
  const controls = useRef<OrbitControlsImpl>(null);

  const bounds = useMemo(() => boundsOf(structures), [structures]);
  const sceneBox = useMemo(() => unionBox(structures, structures.map((s) => s.id)), [structures]);

  // Initial fit once meshes are known.
  const fitted = useRef(false);
  useEffect(() => {
    if (structures.length > 0 && !fitted.current) {
      fitted.current = true;
      requestCamera({ kind: "reset" });
    }
  }, [structures, requestCamera]);

  // Frame whatever gets selected (click, search, chip, breadcrumb, deep link).
  useEffect(() => {
    if (selectedId && structures.length > 0) frameStructure(selectedId);
  }, [selectedId, structures, hierarchy]);

  // Keyboard: F frame selection, Home reset, Esc deselect, 1-5 standard views.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT")) return;
      const { selectedId: sel } = useStore.getState();
      if (e.key === "f" || e.key === "F") sel ? frameStructure(sel) : requestCamera({ kind: "reset" });
      else if (e.key === "Home") requestCamera({ kind: "reset" });
      else if (e.key === "Escape") select(null);
      else if (PRESET_KEYS[e.key]) requestCamera({ kind: "preset", view: PRESET_KEYS[e.key] });
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [requestCamera, select]);

  // Visibility: layer toggles, then the region filter, then isolate/dim relative to the selection.
  const regionMembers = useMemo(
    () => (regionFilter && hierarchy ? subtree(hierarchy, regionFilter) : null),
    [regionFilter, hierarchy],
  );
  const related = useMemo(() => {
    const set = new Set<string>();
    if (highlights.selected) set.add(highlights.selected);
    for (const key of ["antagonists", "synergists", "attachments", "exercise", "referral"] as const)
      for (const id of highlights[key]) set.add(id);
    return set;
  }, [highlights]);
  const focusing = viewMode !== "all" && related.size > 0;

  const visible = structures.filter(
    (s) =>
      ((layers as Record<string, boolean>)[s.type] ?? true) &&
      (!regionMembers || regionMembers.has(s.id)) &&
      !(viewMode === "isolate" && focusing && !related.has(s.id)),
  );
  const hoveredName = structures.find((s) => s.id === hovered)?.name;

  return (
    <div className="relative h-full w-full">
      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.05 }}
        camera={{ position: [0, 0.2, 2.2], fov: 40, near: 0.01, far: 50 }}
        onPointerMissed={(e) => e.type === "click" && select(null)}
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
              dimmed={viewMode === "dim" && focusing && !related.has(s.id)}
              onSelect={select}
              onFocus={(id) => {
                select(id);
                frameStructure(id);
              }}
              onHover={hover}
            />
          ))}
        </Suspense>
        <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={0.1} />
        <CameraRig controls={controls} sceneBox={sceneBox} />
        <GizmoHelper alignment="top-right" margin={[70, 70]}>
          <GizmoViewport axisColors={["#c0504d", "#7fa84a", "#4f81bd"]} labels={["Side", "Up", "Front"]} labelColor="white" />
        </GizmoHelper>
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
