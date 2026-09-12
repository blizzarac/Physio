import { useEffect, useState } from "react";
import { api, type Structure } from "../api";
import { useStore } from "../store";
import { AnatomyTab } from "../tabs/AnatomyTab";
import { ExercisesTab } from "../tabs/ExercisesTab";
import { MobilizationTab, PainTab } from "../tabs/ContentTabs";

const TABS = [
  { key: "anatomy", label: "Anatomy" },
  { key: "exercises", label: "Exercises" },
  { key: "pain", label: "Pain" },
  { key: "mobilization", label: "Mobilization" },
] as const;

export function SidePanel({ structureId }: { structureId: string | null }) {
  const [structure, setStructure] = useState<Structure | null>(null);
  const [error, setError] = useState<string | null>(null);
  const tab = useStore((s) => s.tab);
  const setTab = useStore((s) => s.setTab);

  useEffect(() => {
    if (!structureId) {
      setStructure(null);
      return;
    }
    let cancelled = false;
    setError(null);
    api
      .structure(structureId)
      .then((s) => !cancelled && setStructure(s))
      .catch((e) => !cancelled && setError(String(e)));
    return () => {
      cancelled = true;
    };
  }, [structureId]);

  if (!structureId) {
    return (
      <div className="p-4 text-sm text-neutral-400">
        Click a structure in the viewer or search for one to see its anatomy, exercises, pain patterns and mobilizations.
      </div>
    );
  }
  if (error) return <div className="p-4 text-sm text-red-300">{error}</div>;
  if (!structure) return <div className="p-4 text-sm text-neutral-500">loading…</div>;

  const counts: Record<string, number | undefined> = {
    exercises: structure.counts.exercises,
    pain: structure.counts.pain_patterns,
    mobilization: structure.counts.mobilizations,
  };

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-neutral-800 p-4">
        <div className="text-xs uppercase tracking-wide text-neutral-500">{structure.type}</div>
        <h2 className="text-xl font-semibold">{structure.names.preferred}</h2>
      </header>
      <nav className="flex border-b border-neutral-800 text-sm">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 px-2 py-2 ${tab === t.key ? "border-b-2 border-amber-400 text-amber-200" : "text-neutral-400 hover:text-neutral-200"}`}
          >
            {t.label}
            {counts[t.key] !== undefined && <span className="ml-1 text-xs text-neutral-500">{counts[t.key]}</span>}
          </button>
        ))}
      </nav>
      <div className="flex-1 overflow-auto p-4">
        {tab === "anatomy" && <AnatomyTab structure={structure} />}
        {tab === "exercises" && <ExercisesTab structureId={structure.id} />}
        {tab === "pain" && <PainTab structureId={structure.id} />}
        {tab === "mobilization" && <MobilizationTab structureId={structure.id} />}
      </div>
    </div>
  );
}
