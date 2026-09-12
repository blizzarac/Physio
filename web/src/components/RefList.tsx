import { Link } from "react-router-dom";
import type { Ref } from "../api";

export function RefList({ title, refs }: { title: string; refs?: Ref[] }) {
  if (!refs || refs.length === 0) return null;
  return (
    <div className="mb-3">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{title}</div>
      <ul className="mt-1 flex flex-wrap gap-1">
        {refs.map((r) => (
          <li key={r.id}>
            <Link to={`/s/${r.id}`} className="rounded bg-neutral-800 px-2 py-0.5 text-sm hover:bg-neutral-700">
              {r.name ?? r.id}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
