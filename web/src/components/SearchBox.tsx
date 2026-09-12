import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type SearchHit } from "../api";

// Name / synonym / Latin search; picking a hit opens the structure and jumps the camera to its
// centroid when it has a mesh (design doc §8).
export function SearchBox() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (q.trim().length < 2) {
      setHits([]);
      return;
    }
    const t = setTimeout(() => api.search(q).then(setHits).catch(() => setHits([])), 150);
    return () => clearTimeout(t);
  }, [q]);

  const pick = (h: SearchHit) => {
    setOpen(false);
    setQ("");
    navigate(`/s/${h.id}`); // selection framing happens in the viewer
  };

  return (
    <div className="relative w-full">
      <input
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        placeholder="Search structures (name, synonym, Latin)…"
        className="w-full rounded bg-neutral-800 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-amber-400"
      />
      {open && hits.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded bg-neutral-900 shadow-lg ring-1 ring-neutral-700">
          {hits.map((h) => (
            <li
              key={h.id}
              onMouseDown={() => pick(h)}
              className="cursor-pointer px-3 py-1.5 text-sm hover:bg-neutral-800"
            >
              <span className="text-neutral-100">{h.name}</span>
              <span className="ml-2 text-xs text-neutral-500">{h.type}</span>
              {h.matched_kind !== "preferred" && (
                <span className="ml-2 text-xs text-neutral-500">({h.matched})</span>
              )}
              {!h.has_mesh && <span className="ml-2 text-xs text-neutral-600">no mesh</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
