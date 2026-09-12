import { useEffect, useState } from "react";
import { api, type Exercise } from "../api";
import { useStore } from "../store";

interface Filters { type: string; equipment: string; level: string; role: string }

export function ExercisesTab({ structureId }: { structureId: string }) {
  const [items, setItems] = useState<Exercise[]>([]);
  const [total, setTotal] = useState(0);
  const [options, setOptions] = useState<{ types: string[]; levels: string[]; equipment: string[] }>();
  const [filters, setFilters] = useState<Filters>({ type: "", equipment: "", level: "", role: "" });
  const [open, setOpen] = useState<string | null>(null);
  const setHighlights = useStore((s) => s.setHighlights);

  useEffect(() => {
    api.exerciseFilters().then(setOptions).catch(() => undefined);
  }, []);

  useEffect(() => {
    api
      .exercises({ structure: structureId, ...filters, limit: 100 })
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .catch(() => setItems([]));
  }, [structureId, filters]);

  // Reverse navigation: hovering an exercise tints every muscle it involves.
  const showInvolved = async (ex: Exercise | null) => {
    if (!ex) return setHighlights({ exercise: new Set() });
    const full = await api.exercise(ex.id).catch(() => null);
    setHighlights({ exercise: new Set(full?.structures?.map((s) => s.id) ?? []) });
  };

  const select = (k: keyof Filters, values: string[] | undefined, label: string) => (
    <select
      value={filters[k]}
      onChange={(e) => setFilters({ ...filters, [k]: e.target.value })}
      className="rounded bg-neutral-800 px-2 py-1 text-xs"
    >
      <option value="">{label}</option>
      {values?.map((v) => (
        <option key={v} value={v}>{v}</option>
      ))}
    </select>
  );

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        {select("type", options?.types, "any type")}
        {select("equipment", options?.equipment, "any equipment")}
        {select("level", options?.levels, "any level")}
        {select("role", ["primary", "secondary"], "primary + secondary")}
      </div>
      <div className="mb-2 text-xs text-neutral-500">{total} exercise{total === 1 ? "" : "s"}</div>
      <ul className="space-y-1">
        {items.map((ex) => (
          <li
            key={ex.id}
            className="rounded bg-neutral-800/60 px-3 py-2"
            onMouseEnter={() => showInvolved(ex)}
            onMouseLeave={() => showInvolved(null)}
          >
            <button className="w-full text-left" onClick={() => setOpen(open === ex.id ? null : ex.id)}>
              <span className="text-sm">{ex.name}</span>
              <span className="ml-2 text-xs text-neutral-500">
                {ex.type}{ex.level ? ` · ${ex.level}` : ""}{ex.equipment.length ? ` · ${ex.equipment.join(", ")}` : ""}
                {ex.role === "secondary" ? " · secondary" : ""}
              </span>
            </button>
            {open === ex.id && (
              <div className="mt-2 text-sm">
                {ex.images.length > 0 && (
                  <div className="mb-2 flex gap-2 overflow-x-auto">
                    {ex.images.map((src) => (
                      <img key={src} src={src} alt="" className="h-28 rounded" loading="lazy" />
                    ))}
                  </div>
                )}
                <ol className="list-decimal space-y-1 pl-5">
                  {ex.instructions.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
                <div className="mt-2 text-xs text-neutral-500">
                  Groups: {[...ex.groups.primary, ...ex.groups.secondary].join(", ")} · Source: {ex.source}
                  {ex.source === "free-exercise-db" ? " (public domain)" : ""}
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
