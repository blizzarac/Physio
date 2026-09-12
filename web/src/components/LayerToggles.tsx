import { LAYERS, useStore } from "../store";

export function LayerToggles() {
  const layers = useStore((s) => s.layers);
  const toggle = useStore((s) => s.toggleLayer);
  return (
    <div className="flex flex-wrap gap-2">
      {LAYERS.map((l) => (
        <label key={l.key} className="flex cursor-pointer items-center gap-1 rounded bg-neutral-800 px-2 py-1 text-xs">
          <input type="checkbox" checked={layers[l.key]} onChange={() => toggle(l.key)} />
          {l.label}
        </label>
      ))}
    </div>
  );
}
