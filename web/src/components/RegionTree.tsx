import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ancestors } from "../nav/hierarchy";
import { useStore } from "../store";
import { frameStructure } from "./Viewer";

// Collapsible region tree from the FMA part_of hierarchy. Subtrees with no meshed structure are
// hidden so the tree only offers places you can actually go. Clicking a name opens the
// structure (which also frames it); the target icon restricts the viewer to that subtree.
export function RegionTree() {
  const hierarchy = useStore((s) => s.hierarchy);
  const selectedId = useStore((s) => s.selectedId);
  const regionFilter = useStore((s) => s.regionFilter);
  const setRegionFilter = useStore((s) => s.setRegionFilter);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const navigate = useNavigate();

  // Roots with something to show, biggest subtree first (the body tree before stray leaves).
  const roots = useMemo(
    () =>
      hierarchy
        ? hierarchy.roots
            .filter((r) => (hierarchy.meshCount.get(r) ?? 0) > 0)
            .sort((a, b) => (hierarchy.meshCount.get(b) ?? 0) - (hierarchy.meshCount.get(a) ?? 0))
        : [],
    [hierarchy],
  );

  // Expand roots and any single-child chains below them so the first real level is visible.
  useEffect(() => {
    if (!hierarchy) return;
    setOpen((prev) => {
      if (prev.size) return prev;
      const next = new Set<string>();
      for (const root of roots) {
        let cur: string | undefined = root;
        while (cur) {
          next.add(cur);
          const kids: string[] = (hierarchy.children.get(cur) ?? []).filter((c) => (hierarchy.meshCount.get(c) ?? 0) > 0);
          cur = kids.length === 1 ? kids[0] : undefined;
        }
      }
      return next;
    });
  }, [hierarchy, roots]);

  // Keep the path to the selection, and the selection itself, expanded.
  useEffect(() => {
    if (!hierarchy || !selectedId) return;
    setOpen((prev) => {
      const next = new Set(prev);
      for (const a of ancestors(hierarchy, selectedId)) next.add(a.id);
      next.add(selectedId);
      return next;
    });
  }, [hierarchy, selectedId]);
  if (!hierarchy) return <div className="p-3 text-xs text-neutral-500">loading hierarchy…</div>;

  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const focusRegion = (id: string) => {
    setRegionFilter(regionFilter === id ? null : id);
    frameStructure(id);
  };

  const Node = ({ id, depth }: { id: string; depth: number }) => {
    const n = hierarchy.byId.get(id)!;
    const kids = (hierarchy.children.get(id) ?? []).filter((c) => (hierarchy.meshCount.get(c) ?? 0) > 0);
    const isOpen = open.has(id);
    const isSelected = selectedId === id;
    const isFilter = regionFilter === id;
    return (
      <li>
        <div
          className={`group flex items-center gap-1 rounded px-1 py-0.5 text-sm ${isSelected ? "bg-amber-500/15 text-amber-200" : "hover:bg-neutral-800"}`}
          style={{ paddingLeft: 4 + depth * 12 }}
        >
          <button
            className={`w-4 text-xs text-neutral-500 ${kids.length ? "" : "invisible"}`}
            onClick={() => toggle(id)}
            aria-label={isOpen ? "collapse" : "expand"}
          >
            {isOpen ? "▾" : "▸"}
          </button>
          <button className="flex-1 truncate text-left" onClick={() => navigate(`/s/${id}`)} title={n.name}>
            {n.name}
          </button>
          <span className="text-[10px] text-neutral-600">{hierarchy.meshCount.get(id)}</span>
          {n.type === "region" || kids.length > 0 ? (
            <button
              className={`px-1 text-xs ${isFilter ? "text-amber-300" : "text-neutral-500 opacity-0 group-hover:opacity-100"}`}
              onClick={() => focusRegion(id)}
              title={isFilter ? "Show all regions" : "Show only this region"}
            >
              ◎
            </button>
          ) : null}
        </div>
        {isOpen && kids.length > 0 && (
          <ul>
            {kids.map((c) => (
              <Node key={c} id={c} depth={depth + 1} />
            ))}
          </ul>
        )}
      </li>
    );
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-neutral-800 px-3 py-2 text-xs uppercase tracking-wide text-neutral-500">Regions</div>
      <ul className="flex-1 overflow-auto p-2">
        {roots.map((r) => (
          <Node key={r} id={r} depth={0} />
        ))}
      </ul>
    </div>
  );
}
