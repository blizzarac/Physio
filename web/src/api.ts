// Typed client for the FastAPI backend. All calls are relative to API_BASE so the same
// build works behind a reverse proxy (see vite.config.ts for the dev proxy).

export const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

export type StructureType =
  | "muscle" | "tendon" | "ligament" | "bone" | "joint" | "fascia" | "region";

export interface Attributed { text: string; source: string; license?: string | null; url?: string | null }
export interface Ref { id: string; name: string | null; source?: string }

export interface StructureSummary {
  id: string;
  type: StructureType;
  name: string;
  mesh_url: string | null;
  centroid: [number, number, number] | null;
}

export interface Structure {
  id: string;
  type: StructureType;
  names: { preferred: string; latin: string | null; synonyms: string[] };
  ta2: string | null;
  definition: Attributed | null;
  actions: Attributed[];
  geometry: {
    mesh_ref: string | null;
    mesh_url: string | null;
    centroid: [number, number, number] | null;
    triangles: number | null;
    path: [number, number, number][];
  };
  relations: Record<string, Ref[]>;
  incoming: Record<string, Ref[]>;
  counts: { exercises: number; pain_patterns: number; mobilizations: number };
}

export interface Related {
  antagonists: Ref[];
  synergists: Ref[];
  joints: Ref[];
  attachments: Ref[];
  parts: Ref[];
}

export interface SearchHit {
  id: string;
  name: string;
  type: StructureType;
  matched: string;
  matched_kind: "preferred" | "latin" | "synonym";
  has_mesh: boolean;
  centroid: [number, number, number] | null;
}

export interface Exercise {
  id: string;
  name: string;
  source: string;
  type: "strength" | "stretch" | "activation" | "isometric";
  level: string | null;
  mechanic: string | null;
  equipment: string[];
  instructions: string[];
  images: string[];
  groups: { primary: string[]; secondary: string[] };
  notes: string | null;
  role?: "primary" | "secondary" | null;
  structures?: (Ref & { role: string })[];
}

export interface Source { id: string; title: string; authors?: string; edition?: string; publisher?: string }

export interface PainPattern {
  type: "pain_pattern";
  id: string;
  title: string | null;
  structure: Ref;
  kind: string;
  description: string | null;
  body: string;
  common_causes: string[];
  aggravating: string[];
  relieving: string[];
  referral_regions: Ref[];
  red_flags: string[];
  sources: Source[];
}

export interface Mobilization {
  type: "mobilization";
  id: string;
  title: string | null;
  targets: Ref[];
  joint: Ref | null;
  kind: string;
  body: string;
  steps: string[];
  duration: string | null;
  frequency: string | null;
  contraindications: string[];
  media: string[];
  sources: Source[];
}

export interface ContentResponse<T> { disclaimer: string; items: T[] }

async function get<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
  const url = new URL(API_BASE + path, window.location.origin);
  for (const [k, v] of Object.entries(params ?? {})) if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  structures: (withMesh = true) => get<StructureSummary[]>("/structures", { with_mesh: withMesh }),
  structure: (id: string) => get<Structure>(`/structures/${encodeURIComponent(id)}`),
  related: (id: string) => get<Related>(`/structures/${encodeURIComponent(id)}/related`),
  search: (q: string) => get<SearchHit[]>("/search", { q, limit: 15 }),
  exercises: (params: { structure?: string; type?: string; equipment?: string; level?: string; role?: string; limit?: number; offset?: number }) =>
    get<{ items: Exercise[]; total: number }>("/exercises", params),
  exerciseFilters: () => get<{ types: string[]; levels: string[]; equipment: string[] }>("/exercises/filters"),
  exercise: (id: string) => get<Exercise>(`/exercises/${id}`),
  pain: (id: string) => get<ContentResponse<PainPattern>>(`/pain/${encodeURIComponent(id)}`),
  mobilizations: (id: string) => get<ContentResponse<Mobilization>>(`/mobilizations/${encodeURIComponent(id)}`),
  meshUrl: (meshUrl: string) => API_BASE + meshUrl,
};
