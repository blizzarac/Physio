import { useEffect } from "react";
import { api, type Structure } from "../api";
import { useStore } from "../store";
import { Attribution } from "../components/Attribution";
import { RefList } from "../components/RefList";

export function AnatomyTab({ structure }: { structure: Structure }) {
  const setHighlights = useStore((s) => s.setHighlights);

  // Tint antagonists / synergists / attachments while this structure is open (design doc §8).
  useEffect(() => {
    let cancelled = false;
    api
      .related(structure.id)
      .then((r) => {
        if (cancelled) return;
        setHighlights({
          antagonists: new Set(r.antagonists.map((x) => x.id)),
          synergists: new Set(r.synergists.map((x) => x.id)),
          attachments: new Set(r.attachments.map((x) => x.id)),
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [structure.id, setHighlights]);

  const rel = structure.relations;
  return (
    <div>
      {structure.names.latin && <div className="italic text-neutral-400">{structure.names.latin}</div>}
      {structure.names.synonyms.length > 0 && (
        <div className="mb-3 text-xs text-neutral-500">Also: {structure.names.synonyms.join(", ")}</div>
      )}
      {structure.definition ? (
        <p className="mb-3 text-sm leading-relaxed">
          {structure.definition.text} <Attribution a={structure.definition} />
        </p>
      ) : (
        <p className="mb-3 text-sm text-neutral-500">No definition imported for this structure.</p>
      )}
      {structure.actions.length > 0 && (
        <div className="mb-3">
          <div className="text-xs uppercase tracking-wide text-neutral-500">Actions</div>
          <ul className="mt-1 list-disc pl-5 text-sm">
            {structure.actions.map((a, i) => (
              <li key={i}>
                {a.text} <Attribution a={a} />
              </li>
            ))}
          </ul>
        </div>
      )}
      <RefList title="Origin" refs={rel.origin} />
      <RefList title="Insertion" refs={rel.insertion} />
      <RefList title="Innervation" refs={rel.innervation} />
      <RefList title="Arterial supply" refs={rel.arterial_supply} />
      <RefList title="Crosses joint" refs={rel.crosses_joint} />
      <RefList title="Antagonists" refs={rel.antagonist_of} />
      <RefList title="Synergists" refs={rel.synergist_of} />
      <RefList title="Part of" refs={rel.part_of} />
      <RefList title="Parts" refs={structure.incoming.part_of} />
      <RefList title="Muscles originating here" refs={structure.incoming.origin} />
      <RefList title="Muscles inserting here" refs={structure.incoming.insertion} />
      <RefList title="Muscles crossing this joint" refs={structure.incoming.crosses_joint} />
      <div className="mt-4 text-xs text-neutral-600">
        {structure.id}
        {structure.ta2 ? ` · TA ${structure.ta2}` : ""}
        {structure.geometry.triangles ? ` · ${structure.geometry.triangles} triangles` : ""}
        <br />
        Relations: FMA (CC BY 3.0); geometry: BodyParts3D (CC BY 4.0)
      </div>
    </div>
  );
}
