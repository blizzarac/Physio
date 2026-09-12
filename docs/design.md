---
tags: [design]
created: 2026-09-12
status: draft
---

# Anatomy Explorer — Design Document

## 1. Purpose

A self-hosted tool that renders the human musculoskeletal system in 3D and, for any selected muscle, tendon, or joint, explains:

- its anatomy (attachments, innervation, actions, relationships),
- exercises that train or stretch it,
- common pain patterns associated with it,
- mobilization and self-care techniques.

Open data provides the anatomy and exercise layers. Pain and mobilization content is authored in-house because no open structured dataset exists.

## 2. Goals and non-goals

**Goals**

- Click any structure in a 3D body and get a consolidated, linked explanation.
- Navigate by relationship: muscle → joint it crosses → antagonists → exercises → pain patterns.
- Keep all content addressable by a stable anatomical ID so layers can be added independently.
- Run offline / self-hosted; no dependency on third-party APIs at runtime.

**Non-goals**

- Medical diagnosis or personalised treatment advice.
- Biomechanical simulation (forces, gait). OpenSim data may be imported for geometry only.
- Full-body coverage beyond the musculoskeletal system in v1 (no viscera, vasculature).

## 3. Data sources

| Layer | Source | Format | License | Role |
|---|---|---|---|---|
| Geometry | BodyParts3D (DBCLS, rel. 2025) | OBJ/STL meshes, TSV part lists, IS-A / PART-OF trees | CC BY 4.0 | 3D models, keyed by FMA ID |
| Geometry (alt.) | Z-Anatomy | Blender file | CC BY-SA 4.0 | Fallback for structures missing in BodyParts3D; more labels |
| Semantics | FMA (Foundational Model of Anatomy) | OWL | CC BY 3.0 | Origin, insertion, innervation, arterial supply, part-of hierarchy |
| Semantics | Uberon | OWL/OBO | CC BY 3.0 | Definitions, synonyms, cross-refs to FMA and Wikipedia |
| Descriptions | Wikidata / Wikipedia | SPARQL / REST | CC0 / CC BY-SA | Human-readable summaries, actions, images |
| Muscle paths | OpenSim (Rajagopal 2016) | .osim XML | CC BY 4.0 | Attachment coordinates, muscle path polylines (optional) |
| Exercises | free-exercise-db (yuhonas) | JSON + images | Public domain | ~870 exercises with primary/secondary muscles |
| Exercises (alt.) | wger | REST API / DB dump | AGPL | Multilingual exercise DB |
| Pain / mobilization | Authored | Markdown + YAML | Own | Trigger points, referred pain, mobilization techniques, contraindications |
| ROM norms | Published AAOS / AMA tables | Authored YAML | — | Normal joint ranges for reference |

**Licensing note:** CC BY-SA (Z-Anatomy, Wikipedia text) is viral for derived content. If Z-Anatomy meshes are used, the combined dataset must ship under CC BY-SA. Prefer BodyParts3D + FMA + free-exercise-db for a permissive baseline, and keep Wikipedia text in a clearly separated, attributed field.

## 4. Canonical identifier

Every entity in every layer resolves to an **FMA ID** (e.g. `FMA:22356` = biceps femoris). Reasons:

- BodyParts3D meshes are already labeled with FMA IDs.
- FMA carries the richest relational data.
- Uberon and Wikidata both cross-reference FMA.

Structures without an FMA ID (rare in the MSK domain) get a local ID in an `ax:` namespace with a documented mapping.

## 5. Domain model

```
Structure (FMA ID)
 ├─ type: muscle | tendon | ligament | bone | joint | fascia | region
 ├─ names: preferred, latin (TA2), synonyms[]
 ├─ definition (Uberon / Wikidata, attributed)
 ├─ relations
 │    ├─ part_of[]           (FMA)
 │    ├─ origin[] / insertion[]   (FMA, bone/region IDs)
 │    ├─ innervation[]       (FMA)
 │    ├─ crosses_joint[]     (derived: origin/insertion on different bones)
 │    ├─ antagonist_of[]     (authored)
 │    └─ synergist_of[]      (authored)
 ├─ actions[]                (Wikidata + authored)
 ├─ geometry
 │    ├─ mesh_ref            (BodyParts3D file)
 │    ├─ centroid            (computed from mesh)
 │    └─ path[]              (OpenSim, optional)
 └─ content
      ├─ exercises[]         → Exercise
      ├─ pain_patterns[]     → PainPattern
      └─ mobilizations[]     → Mobilization

Exercise
 ├─ id, name, source (free-exercise-db | wger | authored)
 ├─ primary_structures[] / secondary_structures[]   (FMA IDs)
 ├─ type: strength | stretch | activation | isometric
 ├─ equipment[], level
 ├─ instructions[], images[]
 └─ notes (authored)

PainPattern
 ├─ id, structure (FMA ID)
 ├─ kind: trigger_point | strain | tendinopathy | referral | compression
 ├─ description, common_causes[], aggravating[], relieving[]
 ├─ referral_regions[]       (FMA region IDs — used to paint the mesh)
 ├─ red_flags[]
 └─ sources[]

Mobilization
 ├─ id, targets[] (FMA IDs), joint (FMA ID)
 ├─ kind: self_myofascial | stretch | joint_glide | nerve_glide | isometric
 ├─ steps[], duration, frequency
 ├─ contraindications[]
 └─ media[]
```

## 6. Muscle-name mapping

Exercise databases use informal names (`hamstrings`, `quadriceps`, `lower back`). A hand-curated mapping table expands each informal group to a set of FMA IDs:

```yaml
hamstrings:
  - FMA:22356   # biceps femoris
  - FMA:22357   # semitendinosus
  - FMA:22358   # semimembranosus
```

Around 20 groups cover free-exercise-db entirely. The table is a first-class artifact under version control and is validated at build time (every FMA ID must exist in the FMA import and have a mesh).

## 7. Architecture

```
┌────────────────────────────────────────────────────┐
│ Build pipeline (Python, run offline)               │
│  fetch → parse FMA/Uberon (rdflib) → load BP3D     │
│  → simplify meshes (trimesh, target ≤ 20k tris)    │
│  → compute centroids → import exercises            │
│  → apply mapping table → validate → emit bundle    │
└────────────────────────────────────────────────────┘
                     │
                     ▼
        data bundle: SQLite + static/meshes/*.glb
                     │
                     ▼
┌────────────────────────────────────────────────────┐
│ Backend (FastAPI)                                  │
│  /structures/{fma}   /search   /exercises          │
│  /pain/{fma}         /mobilizations/{fma}          │
│  serves bundle read-only; authored content hot-    │
│  reloaded from Markdown/YAML directory             │
└────────────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────┐
│ Frontend (React + three.js / react-three-fiber)    │
│  3D viewer · picking · layer toggles · highlight   │
│  side panel: anatomy / exercises / pain / mobility │
│  region painting for referral maps                 │
└────────────────────────────────────────────────────┘
```

**Why SQLite over a graph DB:** the relational data is small (tens of thousands of triples in the MSK subset). SQLite with a `relations(subject, predicate, object)` table plus FTS5 covers search and traversal. A graph DB can be introduced later if cross-species or whole-FMA queries are needed.

**Mesh format:** convert BodyParts3D OBJ to glTF/GLB with Draco compression. One file per structure so the viewer loads lazily by region.

## 8. Frontend behaviour

- **Viewer:** full-body model, orbit controls, layer toggles (bones, muscles, tendons/ligaments, joints). Muscles rendered with slight transparency; selected structure highlighted, related structures (antagonists, synergists) tinted.
- **Picking:** GPU-based ID picking; hover shows the name, click opens the panel.
- **Panel tabs:** Anatomy · Exercises · Pain · Mobilization. Each tab shows its own source attribution.
- **Referral painting:** for a PainPattern, its `referral_regions` are painted onto the skin/surface mesh as a heat overlay.
- **Search:** name, synonym, or Latin; jumps the camera to the centroid.
- **Deep links:** `/s/FMA:22356` opens directly on a structure.

## 9. Authored content workflow

Pain and mobilization content lives in a `content/` directory as Markdown with YAML frontmatter, one file per entry:

```markdown
---
type: pain_pattern
id: pp-upper-trapezius-tp1
structure: FMA:32557
kind: trigger_point
referral_regions: [FMA:24997, FMA:48598]
sources: [travell-simons-vol1-ch6]
---
Tenderness in the upper fibres of trapezius, commonly referring…
```

- Validated at build time against the FMA import (every referenced ID must exist).
- Each entry needs at least one `source` so provenance is visible in the UI.
- A standard disclaimer block is rendered on every Pain and Mobilization tab.

## 10. Phased delivery

**Phase 1 — Anatomy viewer**
- Build pipeline for BodyParts3D + FMA MSK subset.
- three.js viewer with picking, layers, search.
- Anatomy tab populated from FMA + Uberon definitions.

**Phase 2 — Exercises**
- Import free-exercise-db, apply mapping table.
- Exercises tab with filters (type, equipment, level).
- Reverse navigation: exercise → highlight all involved muscles.

**Phase 3 — Pain and mobilization**
- Content schema, validation, hot-reload.
- Referral painting on the surface mesh.
- Author an initial set (e.g. 20 muscles with the highest clinical frequency: trapezius, levator scapulae, gluteus medius, piriformis, iliopsoas, quadratus lumborum, …).

**Phase 4 — Refinement**
- OpenSim muscle paths for line-of-pull display.
- Joint ROM overlay with normal ranges.
- Multilingual names (Uberon/Wikidata labels, DE/EN/EL).

## 11. Risks and open questions

- **Content effort.** Pain and mobilization authoring is the real cost; the data plumbing is a few weeks, the content is ongoing.
- **BodyParts3D granularity.** Some muscles are single meshes where FMA distinguishes heads or parts. Decide whether to split meshes (effort) or map several FMA IDs to one mesh (simpler; lose precision).
- **Tendons.** BodyParts3D has limited tendon coverage; tendons may need to be represented as attachment-point annotations rather than meshes.
- **Mesh size.** Full-body muscles total several hundred MB of OBJ. Decimation and per-region lazy loading are required for a usable web build.
- **Liability.** Content must be clearly framed as educational. Consider requiring an explicit acknowledgement before showing pain content.
- **Open:** single user or multi-user? If multi-user, add auth and per-user notes/favourites.
- **Open:** should the authored content itself be published under an open license to invite contributions?

## 12. Initial tech decisions

- Python 3.12 build pipeline: `rdflib`, `trimesh`, `pygltflib`, `pandas`
- Backend: FastAPI + SQLite (FTS5)
- Frontend: React, react-three-fiber, drei, Zustand for state, Tailwind
- Content: Markdown + YAML, validated with `pydantic` schemas
- Repo layout: `pipeline/`, `api/`, `web/`, `content/`, `mapping/`
