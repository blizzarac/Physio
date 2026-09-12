import { create } from "zustand";
import type { StructureType } from "./api";

export type Layer = Extract<StructureType, "bone" | "muscle" | "tendon" | "ligament" | "joint">;
export const LAYERS: { key: Layer; label: string }[] = [
  { key: "bone", label: "Bones" },
  { key: "muscle", label: "Muscles" },
  { key: "tendon", label: "Tendons" },
  { key: "ligament", label: "Ligaments" },
  { key: "joint", label: "Joints" },
];

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
  selectedId: string | null;
  hoveredId: string | null;
  layers: Record<Layer, boolean>;
  highlights: Highlights;
  cameraTarget: [number, number, number] | null;
  tab: "anatomy" | "exercises" | "pain" | "mobilization";
  select: (id: string | null) => void;
  hover: (id: string | null) => void;
  toggleLayer: (layer: Layer) => void;
  setHighlights: (patch: Partial<Highlights>) => void;
  flyTo: (target: [number, number, number] | null) => void;
  setTab: (tab: State["tab"]) => void;
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
  selectedId: null,
  hoveredId: null,
  layers: { bone: true, muscle: true, tendon: true, ligament: true, joint: false },
  highlights: emptyHighlights(),
  cameraTarget: null,
  tab: "anatomy",
  select: (id) => set({ selectedId: id, highlights: { ...emptyHighlights(), selected: id } }),
  hover: (id) => set({ hoveredId: id }),
  toggleLayer: (layer) => set((s) => ({ layers: { ...s.layers, [layer]: !s.layers[layer] } })),
  setHighlights: (patch) => set((s) => ({ highlights: { ...s.highlights, ...patch } })),
  flyTo: (target) => set({ cameraTarget: target }),
  setTab: (tab) => set({ tab }),
}));
