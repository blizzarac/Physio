import { useEffect, useState } from "react";
import { api, type Mobilization, type PainPattern, type Source } from "../api";
import { useStore } from "../store";
import { RefList } from "../components/RefList";

function Bullets({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="mb-2">
      <div className="text-xs uppercase tracking-wide text-neutral-500">{title}</div>
      <ul className="mt-1 list-disc pl-5 text-sm">
        {items.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
    </div>
  );
}

function Sources({ sources }: { sources: Source[] }) {
  return (
    <div className="mt-2 text-xs text-neutral-500">
      Sources:{" "}
      {sources.map((s) => `${s.authors ? s.authors + ", " : ""}${s.title}${s.edition ? ", " + s.edition : ""}`).join("; ")}
    </div>
  );
}

function Disclaimer({ text }: { text: string }) {
  if (!text) return null;
  return <p className="mb-3 rounded border border-amber-700/50 bg-amber-900/20 p-2 text-xs text-amber-200">{text}</p>;
}

// Referral painting (§8): while a pain pattern is hovered, its referral regions are tinted red.
// Painting onto a skin/surface mesh is a Phase 3 item; tinting the region meshes is the v1 form.
export function PainTab({ structureId }: { structureId: string }) {
  const [data, setData] = useState<{ disclaimer: string; items: PainPattern[] }>();
  const setHighlights = useStore((s) => s.setHighlights);
  useEffect(() => {
    api.pain(structureId).then(setData).catch(() => setData({ disclaimer: "", items: [] }));
  }, [structureId]);
  if (!data) return null;
  return (
    <div>
      <Disclaimer text={data.disclaimer} />
      {data.items.length === 0 && <p className="text-sm text-neutral-500">No pain patterns authored for this structure yet.</p>}
      {data.items.map((p) => (
        <article
          key={p.id}
          className="mb-4 rounded bg-neutral-800/60 p-3"
          onMouseEnter={() => setHighlights({ referral: new Set(p.referral_regions.map((r) => r.id)) })}
          onMouseLeave={() => setHighlights({ referral: new Set() })}
        >
          <h3 className="text-base font-medium">{p.title ?? p.id}</h3>
          <div className="mb-2 text-xs text-neutral-500">
            {p.kind.replace("_", " ")} · {p.structure.name ?? p.structure.id}
          </div>
          <p className="mb-2 whitespace-pre-line text-sm leading-relaxed">{p.body}</p>
          <RefList title="Referral regions" refs={p.referral_regions} />
          <Bullets title="Common causes" items={p.common_causes} />
          <Bullets title="Aggravating" items={p.aggravating} />
          <Bullets title="Relieving" items={p.relieving} />
          {p.red_flags.length > 0 && (
            <div className="mb-2 rounded border border-red-800/60 p-2">
              <Bullets title="Red flags — seek assessment" items={p.red_flags} />
            </div>
          )}
          <Sources sources={p.sources} />
        </article>
      ))}
    </div>
  );
}

export function MobilizationTab({ structureId }: { structureId: string }) {
  const [data, setData] = useState<{ disclaimer: string; items: Mobilization[] }>();
  useEffect(() => {
    api.mobilizations(structureId).then(setData).catch(() => setData({ disclaimer: "", items: [] }));
  }, [structureId]);
  if (!data) return null;
  return (
    <div>
      <Disclaimer text={data.disclaimer} />
      {data.items.length === 0 && <p className="text-sm text-neutral-500">No mobilizations authored for this structure yet.</p>}
      {data.items.map((m) => (
        <article key={m.id} className="mb-4 rounded bg-neutral-800/60 p-3">
          <h3 className="text-base font-medium">{m.title ?? m.id}</h3>
          <div className="mb-2 text-xs text-neutral-500">
            {m.kind.replace("_", " ")}
            {m.duration ? ` · ${m.duration}` : ""}
            {m.frequency ? ` · ${m.frequency}` : ""}
          </div>
          <p className="mb-2 whitespace-pre-line text-sm leading-relaxed">{m.body}</p>
          <RefList title="Targets" refs={m.targets} />
          {m.joint && <RefList title="Joint" refs={[m.joint]} />}
          {m.steps.length > 0 && (
            <ol className="mb-2 list-decimal space-y-1 pl-5 text-sm">
              {m.steps.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          )}
          <Bullets title="Contraindications" items={m.contraindications} />
          <Sources sources={m.sources} />
        </article>
      ))}
    </div>
  );
}
