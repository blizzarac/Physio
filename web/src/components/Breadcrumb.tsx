import { Link } from "react-router-dom";
import { ancestors } from "../nav/hierarchy";
import { useStore } from "../store";

// Region chain above the structure name: Human body › Lower limb › Thigh › …
export function Breadcrumb({ id }: { id: string }) {
  const hierarchy = useStore((s) => s.hierarchy);
  if (!hierarchy) return null;
  const chain = ancestors(hierarchy, id);
  if (chain.length === 0) return null;
  return (
    <nav className="mb-1 flex flex-wrap items-center gap-1 text-xs text-neutral-400" aria-label="Region">
      {chain.map((a, i) => (
        <span key={a.id} className="flex items-center gap-1">
          {i > 0 && <span className="text-neutral-600">›</span>}
          <Link to={`/s/${a.id}`} className="hover:text-neutral-200 hover:underline">
            {a.name}
          </Link>
        </span>
      ))}
    </nav>
  );
}
