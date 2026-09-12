import type { HierarchyNode } from "../api";

// Index over the flat /hierarchy list: parent links, children lists, and per-node counts of
// meshed descendants (used to hide empty subtrees and to frame a region).
export interface HierarchyIndex {
  byId: Map<string, HierarchyNode>;
  children: Map<string, string[]>;
  roots: string[];
  meshCount: Map<string, number>; // meshed structures in the subtree, self included
}

export function buildIndex(nodes: HierarchyNode[]): HierarchyIndex {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const children = new Map<string, string[]>();
  const roots: string[] = [];
  for (const n of nodes) {
    if (n.parent && byId.has(n.parent)) {
      const list = children.get(n.parent) ?? [];
      list.push(n.id);
      children.set(n.parent, list);
    } else roots.push(n.id);
  }
  for (const list of children.values()) list.sort((a, b) => byId.get(a)!.name.localeCompare(byId.get(b)!.name));
  roots.sort((a, b) => byId.get(a)!.name.localeCompare(byId.get(b)!.name));

  const meshCount = new Map<string, number>();
  const count = (id: string, trail: Set<string>): number => {
    if (meshCount.has(id)) return meshCount.get(id)!;
    if (trail.has(id)) return 0;
    trail.add(id);
    let c = byId.get(id)?.has_mesh ? 1 : 0;
    for (const ch of children.get(id) ?? []) c += count(ch, trail);
    meshCount.set(id, c);
    return c;
  };
  for (const id of byId.keys()) count(id, new Set());
  return { byId, children, roots, meshCount };
}

/** Ancestors from the root down to the direct parent (excludes the node itself). */
export function ancestors(index: HierarchyIndex, id: string): HierarchyNode[] {
  const out: HierarchyNode[] = [];
  const seen = new Set<string>([id]);
  let cur = index.byId.get(id)?.parent ?? null;
  while (cur && !seen.has(cur)) {
    const n = index.byId.get(cur);
    if (!n) break;
    out.unshift(n);
    seen.add(cur);
    cur = n.parent;
  }
  return out;
}

/** The node itself plus every descendant. */
export function subtree(index: HierarchyIndex, id: string): Set<string> {
  const out = new Set<string>();
  const stack = [id];
  while (stack.length) {
    const cur = stack.pop()!;
    if (out.has(cur)) continue;
    out.add(cur);
    for (const ch of index.children.get(cur) ?? []) stack.push(ch);
  }
  return out;
}
