"""FastAPI app: serves the read-only bundle plus hot-reloaded authored content (§7).

Routes
------
GET /structures                 list (filter: type, with_mesh)
GET /structures/{id}            structure + relations + counts of linked content
GET /structures/{id}/related    antagonists / synergists / joints / bones for highlighting
GET /search?q=                  FTS over preferred names, Latin names, synonyms
GET /exercises                  filter by structure, type, equipment, level
GET /exercises/{id}
GET /exercises/filters
GET /pain/{id}                  pain patterns for a structure (as source or referral region)
GET /mobilizations/{id}
GET /content/status             parse/reference errors of the authored content
GET /meta
/static/meshes/*.glb            per-structure GLB files
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.content import ContentStore
from api.db import Bundle
from pipeline.config import REPO_ROOT
from pipeline.ids import normalize_id

log = logging.getLogger(__name__)


def create_app(
    bundle_dir: Path | None = None, content_dir: Path | None = None, watch: bool = True
) -> FastAPI:
    bundle_dir = bundle_dir or Path(
        os.environ.get("ANATOMY_BUNDLE_DIR", REPO_ROOT / "data" / "bundle")
    )
    content_dir = content_dir or Path(os.environ.get("ANATOMY_CONTENT_DIR", REPO_ROOT / "content"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        bundle = Bundle(bundle_dir / "anatomy.sqlite")
        store = ContentStore(content_dir, bundle.structure_ids())
        if watch and content_dir.exists():
            store.start_watching()
        app.state.bundle, app.state.content = bundle, store
        try:
            yield
        finally:
            store.stop()
            bundle.close()

    app = FastAPI(title="Anatomy Explorer API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("ANATOMY_CORS_ORIGINS", "http://localhost:5173").split(","),
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    meshes = bundle_dir / "static" / "meshes"
    meshes.mkdir(parents=True, exist_ok=True)
    app.mount("/static/meshes", StaticFiles(directory=meshes), name="meshes")

    def _id(value: str) -> str:
        try:
            return normalize_id(value)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    def _bundle(request: Request) -> Bundle:
        return request.app.state.bundle

    def _content(request: Request) -> ContentStore:
        return request.app.state.content

    @app.get("/meta")
    def meta(request: Request):
        b = _bundle(request)
        return {**b.meta(), "content": _content(request).status()}

    @app.get("/structures")
    def list_structures(request: Request, type: str | None = None, with_mesh: bool = False):
        return _bundle(request).list_structures(type, with_mesh)

    @app.get("/structures/{structure_id}")
    def get_structure(request: Request, structure_id: str):
        sid = _id(structure_id)
        b, c = _bundle(request), _content(request)
        s = b.structure(sid)
        if s is None:
            raise HTTPException(404, f"unknown structure {sid}")
        s["relations"] = b.relations(sid)
        s["incoming"] = b.incoming(sid)
        _, n_ex = b.exercises(sid, None, None, None, None, 1, 0)
        s["counts"] = {
            "exercises": n_ex,
            "pain_patterns": len(c.pain_for(sid, b.label)),
            "mobilizations": len(c.mobilizations_for(sid, b.label)),
        }
        return s

    @app.get("/structures/{structure_id}/related")
    def related(request: Request, structure_id: str):
        """IDs to tint in the viewer when this structure is selected."""
        sid = _id(structure_id)
        b = _bundle(request)
        if b.structure(sid) is None:
            raise HTTPException(404, f"unknown structure {sid}")
        rel = b.relations(sid)
        return {
            "antagonists": rel.get("antagonist_of", []),
            "synergists": rel.get("synergist_of", []),
            "joints": rel.get("crosses_joint", []),
            "attachments": rel.get("origin", []) + rel.get("insertion", []),
            "parts": b.incoming(sid).get("part_of", []),
        }

    @app.get("/search")
    def search(request: Request, q: str = Query(min_length=1), limit: int = Query(20, le=100)):
        return _bundle(request).search(q, limit)

    @app.get("/exercises/filters")
    def exercise_filters(request: Request):
        return _bundle(request).exercise_filters()

    @app.get("/exercises")
    def list_exercises(
        request: Request,
        structure: str | None = None,
        type: str | None = None,
        equipment: str | None = None,
        level: str | None = None,
        role: str | None = Query(None, pattern="^(primary|secondary)$"),
        limit: int = Query(50, le=200),
        offset: int = 0,
    ):
        sid = _id(structure) if structure else None
        items, total = _bundle(request).exercises(sid, type, equipment, level, role, limit, offset)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @app.get("/exercises/{exercise_id:path}")
    def get_exercise(request: Request, exercise_id: str):
        ex = _bundle(request).exercise(exercise_id)
        if ex is None:
            raise HTTPException(404, f"unknown exercise {exercise_id}")
        return ex

    @app.get("/pain")
    def all_pain(request: Request):
        c = _content(request)
        return {"disclaimer": c.snapshot.disclaimer, "items": c.all_pain(_bundle(request).label)}

    @app.get("/pain/{structure_id}")
    def pain(request: Request, structure_id: str):
        sid = _id(structure_id)
        c = _content(request)
        return {
            "disclaimer": c.snapshot.disclaimer,
            "items": c.pain_for(sid, _bundle(request).label),
        }

    @app.get("/mobilizations")
    def all_mobilizations(request: Request):
        c = _content(request)
        return {
            "disclaimer": c.snapshot.disclaimer,
            "items": c.all_mobilizations(_bundle(request).label),
        }

    @app.get("/mobilizations/{structure_id}")
    def mobilizations(request: Request, structure_id: str):
        sid = _id(structure_id)
        c = _content(request)
        return {
            "disclaimer": c.snapshot.disclaimer,
            "items": c.mobilizations_for(sid, _bundle(request).label),
        }

    @app.get("/content/status")
    def content_status(request: Request):
        return _content(request).status()

    @app.post("/content/reload")
    def content_reload(request: Request):
        _content(request).reload()
        return _content(request).status()

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=os.environ.get("ANATOMY_HOST", "127.0.0.1"),
        port=int(os.environ.get("ANATOMY_PORT", "8000")),
        reload=False,
    )
