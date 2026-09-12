import { frameStructure } from "./Viewer";
import { useStore, type ViewMode, type ViewPreset } from "../store";

const PRESETS: { view: ViewPreset; label: string; key: string }[] = [
  { view: "anterior", label: "Front", key: "1" },
  { view: "posterior", label: "Back", key: "2" },
  { view: "left", label: "Left", key: "3" },
  { view: "right", label: "Right", key: "4" },
  { view: "superior", label: "Top", key: "5" },
];
const MODES: { mode: ViewMode; label: string; hint: string }[] = [
  { mode: "all", label: "All", hint: "Show everything" },
  { mode: "dim", label: "Dim others", hint: "Fade structures unrelated to the selection" },
  { mode: "isolate", label: "Isolate", hint: "Hide structures unrelated to the selection" },
];

const btn = "rounded bg-neutral-800 px-2 py-1 text-xs hover:bg-neutral-700";
const active = "rounded bg-amber-500/20 px-2 py-1 text-xs text-amber-200 ring-1 ring-amber-500/50";

export function ViewControls() {
  const requestCamera = useStore((s) => s.requestCamera);
  const selectedId = useStore((s) => s.selectedId);
  const viewMode = useStore((s) => s.viewMode);
  const setViewMode = useStore((s) => s.setViewMode);
  const regionFilter = useStore((s) => s.regionFilter);
  const setRegionFilter = useStore((s) => s.setRegionFilter);
  const hierarchy = useStore((s) => s.hierarchy);
  const treeOpen = useStore((s) => s.treeOpen);
  const setTreeOpen = useStore((s) => s.setTreeOpen);
  const regionName = regionFilter ? hierarchy?.byId.get(regionFilter)?.name ?? regionFilter : null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button className={treeOpen ? active : btn} onClick={() => setTreeOpen(!treeOpen)} title="Browse regions">
        Regions
      </button>
      <span className="mx-1 border-l border-neutral-700" />
      {PRESETS.map((p) => (
        <button key={p.view} className={btn} title={`${p.label} view (${p.key})`} onClick={() => requestCamera({ kind: "preset", view: p.view })}>
          {p.label}
        </button>
      ))}
      <button className={btn} title="Frame selection (F)" disabled={!selectedId} onClick={() => selectedId && frameStructure(selectedId)}>
        Frame
      </button>
      <button className={btn} title="Reset view (Home)" onClick={() => requestCamera({ kind: "reset" })}>
        Reset
      </button>
      <span className="mx-1 border-l border-neutral-700" />
      {MODES.map((m) => (
        <button key={m.mode} className={viewMode === m.mode ? active : btn} title={m.hint} onClick={() => setViewMode(m.mode)}>
          {m.label}
        </button>
      ))}
      {regionName && (
        <button className={active} title="Showing only this region; click to show all" onClick={() => setRegionFilter(null)}>
          {regionName} ×
        </button>
      )}
    </div>
  );
}
