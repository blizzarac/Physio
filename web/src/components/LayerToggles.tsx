import { LAYERS, useStore } from "../store";

export function LayerToggles() {
  const layers = useStore((s) => s.layers);
  const toggle = useStore((s) => s.toggleLayer);
  const xray = useStore((s) => s.xray);
  const toggleXray = useStore((s) => s.toggleXray);
  const effects = useStore((s) => s.effects);
  const toggleEffects = useStore((s) => s.toggleEffects);
  return (
    <div className="flex flex-wrap gap-2">
      {LAYERS.map((l) => (
        <label key={l.key} className="flex cursor-pointer items-center gap-1 rounded bg-neutral-800 px-2 py-1 text-xs">
          <input type="checkbox" checked={layers[l.key]} onChange={() => toggle(l.key)} />
          {l.label}
        </label>
      ))}
      <span className="mx-1 border-l border-neutral-700" />
      <label className="flex cursor-pointer items-center gap-1 rounded bg-neutral-800 px-2 py-1 text-xs">
        <input type="checkbox" checked={xray} onChange={toggleXray} />
        See-through muscles
      </label>
      <label className="flex cursor-pointer items-center gap-1 rounded bg-neutral-800 px-2 py-1 text-xs">
        <input type="checkbox" checked={effects} onChange={toggleEffects} />
        Ambient occlusion
      </label>
    </div>
  );
}
