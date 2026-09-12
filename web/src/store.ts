import { create } from "zustand";
import { api, type BBox, type StructureSummary, type StructureType } from "./api";
import { buildIndex, type HierarchyIndex } from "./nav/hierarchy";

export type Layer = Extract<StructureType, "bone" | "muscle" | "tendon" | "ligament" | "joint">;
export const LAYERS: { key: Layer; label: string }[] = [
  { key: "bone", label: "Bones" },
  { key: "muscle", label: "Muscles" },
  { key: "tendon", label: "Tendons" },
  { key: "ligament", label: "Ligaments" },
  { key: "joint", label: "Joints" },
];

export type ViewPreset = "anterior" | "posterior" | "left" | "right" | "superior";
export type ViewMode = "all" | "dim" | "isolate";

// One-shot camera commands consumed by the viewer's camera rig.
export type CameraRequest =
  | { kind: "frame"; box: BBox; preset?: ViewPreset } // fit a box, keeping the current direction
  | { kind: "preset"; view: ViewPreset }              // turn to a standard view around the current target
  | { kind: "reset" };                                // full body, anterior view

// Tints applied in the viewer. A structure can be in several sets; priority is
// selected > referral > antagonist > synergist > exercise > attachment.
export interface Highlights {
  selected: string | null;
  antagonists: Set<string>;
  synergists: Set<string>;
  attachments: Set<string>;
  exercise: Set<string>;   // muscles involved in the hovered exercise (reverse navigation)
  referral: Set<string>;   // referral regions of the hovered pain pattern
}

interface State {
  structures: StructureSummary[];
  structuresError: string | null;
  hierarchy: HierarchyIndex | null;
  selectedId: string | null;
  hoveredId: string | null;
  layers: Record<Layer, boolean>;
  highlights: Highlights;
  cameraRequest: CameraRequest | null;
  viewMode: ViewMode;
  regionFilter: string | null; // show only this region's subtree
  treeOpen: boolean;
  tab: "anatomy" | "exercises" | "pain" | "mobilization";
  xray: boolean;     // see-through muscles so bones and deep structures show
  effects: boolean;  // ambient occlusion + anti-aliasing post-processing
  load: () => Promise<void>;
  select: (id: string | null) => void;
  hover: (id: string | null) => void;
  toggleLayer: (layer: Layer) => void;
  setHighlights: (patch: Partial<Highlights>) => void;
  requestCamera: (req: CameraRequest | null) => void;
  setViewMode: (mode: ViewMode) => void;
  setRegionFilter: (id: string | null) => void;
  setTreeOpen: (open: boolean) => void;
  setTab: (tab: State["tab"]) => void;
  toggleXray: () => void;
  toggleEffects: () => void;
}

const emptyHighlights = (): Highlights => ({
  selected: null,
  antagonists: new Set(),
  synergists: new Set(),
  attachments: new Set(),
  exercise: new Set(),
  referral: new Set(),
});

export const useStore = create<State>((set) => ({
  structures: [],
  structuresError: null,
  hierarchy: null,
  selectedId: null,
  hoveredId: null,
  layers: { bone: true, muscle: true, tendon: true, ligament: true, joint: false },
  highlights: emptyHighlights(),
  cameraRequest: null,
  viewMode: "all",
  regionFilter: null,
  treeOpen: false,
  tab: "anatomy",
  xray: false,
  effects: true,
  load: async () => {
    try {
      const [structures, nodes] = await Promise.all([api.structures(true), api.hierarchy()]);
      set({ structures, hierarchy: buildIndex(nodes), structuresError: null });
    } catch (e) {
      set({ structuresError: String(e) });
    }
  },
  select: (id) => set({ selectedId: id, highlights: { ...emptyHighlights(), selected: id } }),
  hover: (id) => set({ hoveredId: id }),
  toggleLayer: (layer) => set((s) => ({ layers: { ...s.layers, [layer]: !s.layers[layer] } })),
  setHighlights: (patch) => set((s) => ({ highlights: { ...s.highlights, ...patch } })),
  requestCamera: (req) => set({ cameraRequest: req }),
  setViewMode: (viewMode) => set({ viewMode }),
  setRegionFilter: (regionFilter) => set({ regionFilter }),
  setTreeOpen: (treeOpen) => set({ treeOpen }),
  setTab: (tab) => set({ tab }),
  toggleXray: () => set((s) => ({ xray: !s.xray })),
  toggleEffects: () => set((s) => ({ effects: !s.effects })),
}));

/** Union bounding box of the given structures' meshes, or null if none has one. */
export function unionBox(structures: StructureSummary[], ids: Iterable<string>): BBox | null {
  const want = new Set(ids);
  let box: BBox | null = null;
  for (const s of structures) {
    if (!want.has(s.id) || !s.bbox) continue;
    if (!box) box = { min: [...s.bbox.min], max: [...s.bbox.max] };
    else
      for (let i = 0; i < 3; i++) {
        box.min[i] = Math.min(box.min[i], s.bbox.min[i]);
        box.max[i] = Math.max(box.max[i], s.bbox.max[i]);
      }
  }
  return box;
}
