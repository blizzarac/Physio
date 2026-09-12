# Anatomy Explorer

A self-hosted tool that renders the human musculoskeletal system in 3D and, for any
selected muscle, tendon, bone or joint, explains its anatomy, the exercises that train
or stretch it, associated pain patterns, and mobilization techniques. Anatomy and
exercise data come from open datasets; pain and mobilization content is authored in
this repository. See [`docs/design.md`](docs/design.md) for the full design.

```
pipeline/   Python build pipeline: open data -> validated SQLite + GLB bundle
api/        FastAPI backend serving the bundle and hot-reloaded authored content
web/        React + react-three-fiber viewer
content/    authored pain-pattern and mobilization entries (Markdown + YAML)
mapping/    hand-curated tables gluing the layers together (muscle groups, joints, …)
tests/      fixture-based end-to-end tests for pipeline and API
docs/       design document
```

Every entity is keyed by an **FMA ID** (`FMA:22356` = biceps femoris); see `pipeline/ids.py`.

## Quick start

Requirements: Python ≥ 3.11, Node ≥ 20, [uv](https://docs.astral.sh/uv/) (or pip).

```bash
uv venv && uv pip install -e ".[dev]"      # add ",mesh" for decimation of large meshes
cd web && npm install && cd ..
```

### 1. Fetch sources

```bash
.venv/bin/anatomy-build fetch --exercises --uberon --bp3d
BIOPORTAL_API_KEY=… .venv/bin/anatomy-build fetch --fma      # FMA needs a free BioPortal key
.venv/bin/anatomy-build fetch --wikidata                     # optional: actions, images
```

Sources land in `data/raw/` (git-ignored). If you already have `fma.owl`, skip the
key and pass `--fma-file path/to/fma.owl` to `build`.

### 2. Validate, then build

```bash
.venv/bin/anatomy-build validate     # mapping tables + content against the FMA import
.venv/bin/anatomy-build build        # writes data/bundle/anatomy.sqlite + static/meshes/*.glb
```

`validate` and `build` refuse to emit a bundle if any mapping entry or content file
references an unknown FMA ID, if a mapping entry's `expect_name` does not match the
FMA name, or if a content entry lacks a source. The first FMA parse is slow (the OWL is
~300 MB); the extracted MSK subset is cached under `data/cache/`.

### 3. Run

```bash
.venv/bin/anatomy-api                    # http://127.0.0.1:8000  (docs at /docs)
cd web && npm run dev                    # http://127.0.0.1:5173, proxies /api -> :8000
```

Deep links: `http://127.0.0.1:5173/s/FMA:22356`.

For a self-hosted build, `npm run build` produces `web/dist/`; serve it and reverse-proxy
`/api/` to the API (or set `VITE_API_BASE` at build time). Environment variables for the
API: `ANATOMY_BUNDLE_DIR`, `ANATOMY_CONTENT_DIR`, `ANATOMY_HOST`, `ANATOMY_PORT`,
`ANATOMY_CORS_ORIGINS`.

### Try it without the real datasets

The test fixtures include a tiny FMA/Uberon subset and two exercises; box meshes stand
in for BodyParts3D:

```bash
mkdir -p /tmp/bp3d
.venv/bin/python -c "import trimesh as t; t.creation.box(extents=(60,420,60)).export('/tmp/bp3d/FMA24474.obj'); t.creation.box(extents=(40,380,30)).export('/tmp/bp3d/FMA22356.obj')"
.venv/bin/anatomy-build build --fma-file tests/fixtures/fma_mini.ttl \
  --uberon-file tests/fixtures/uberon_mini.ttl --exercises-file tests/fixtures/exercises_mini.json \
  --bodyparts3d-dir /tmp/bp3d --mapping-dir tests/fixtures/mapping --content-dir tests/fixtures/content
ANATOMY_CONTENT_DIR=tests/fixtures/content .venv/bin/anatomy-api
```

## Authoring content

Add a Markdown file under `content/pain/` or `content/mobilization/` with YAML
frontmatter (schema in `pipeline/schemas.py`, examples in the directory). Every entry
needs at least one `sources` key that exists in `content/sources.yaml`. The running API
picks up changes immediately and reports problems at `GET /content/status`; run
`anatomy-build validate` before committing.

## Development

```bash
.venv/bin/pytest                 # pipeline + API tests on fixtures
.venv/bin/ruff check . && .venv/bin/ruff format --check .
cd web && npm run typecheck
```

## Status

| Phase (design doc §10) | State |
|---|---|
| 1 — Anatomy viewer | Pipeline, API, viewer, picking, layers, search, deep links implemented. Not yet run against the full FMA/BodyParts3D export; the FMA IDs in `mapping/` still need that first `validate` run. Picking is raycast-based; GPU ID picking is a later optimisation. |
| 2 — Exercises | free-exercise-db import, mapping table, filters and reverse highlighting implemented. |
| 3 — Pain and mobilization | Schema, validation, hot reload and an initial set of entries implemented. Referral "painting" currently tints the region meshes; a skin-surface heat overlay is still open. |
| 4 — Refinement | Not started (OpenSim paths, ROM overlay, multilingual names). |

## Licenses of the data

FMA (CC BY 3.0), Uberon (CC BY 3.0), BodyParts3D (CC BY 4.0), free-exercise-db (public
domain), Wikidata (CC0). Wikipedia text (CC BY-SA) is kept in a separately attributed
field if imported. Authored content in `content/` is the repository's own.
