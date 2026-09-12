"""Read-only access to the SQLite bundle."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Bundle:
    def __init__(self, db_path: Path):
        if not db_path.exists():
            raise FileNotFoundError(f"bundle not found: {db_path} (run `anatomy-build build`)")
        self.path = db_path
        # check_same_thread=False: FastAPI may serve from a threadpool; access is read-only.
        self.con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
        self.con.row_factory = sqlite3.Row

    def close(self) -> None:
        self.con.close()

    # -- helpers -------------------------------------------------------------------------
    def _rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self.con.execute(sql, params).fetchall()

    def meta(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in self._rows("SELECT key, value FROM meta")}

    def label(self, structure_id: str) -> str | None:
        row = self.con.execute(
            "SELECT preferred AS name FROM structures WHERE id=? "
            "UNION ALL SELECT name FROM labels WHERE id=?",
            (structure_id, structure_id),
        ).fetchone()
        return row["name"] if row else None

    def structure_ids(self) -> set[str]:
        return {r["id"] for r in self._rows("SELECT id FROM structures")}

    @staticmethod
    def _bbox(row: sqlite3.Row) -> dict[str, list[float]] | None:
        if row["bbox_min_x"] is None:
            return None
        return {
            "min": [row["bbox_min_x"], row["bbox_min_y"], row["bbox_min_z"]],
            "max": [row["bbox_max_x"], row["bbox_max_y"], row["bbox_max_z"]],
        }

    # -- structures ------------------------------------------------------------------------
    def structure(self, structure_id: str) -> dict[str, Any] | None:
        row = self.con.execute("SELECT * FROM structures WHERE id=?", (structure_id,)).fetchone()
        if row is None:
            return None
        names = self._rows(
            "SELECT name, kind FROM names WHERE structure_id=? AND kind='synonym'", (structure_id,)
        )
        return {
            "id": row["id"],
            "type": row["type"],
            "names": {
                "preferred": row["preferred"],
                "latin": row["latin"],
                "synonyms": [n["name"] for n in names],
            },
            "ta2": row["ta2"],
            "definition": json.loads(row["definition"]) if row["definition"] else None,
            "actions": json.loads(row["actions"]),
            "geometry": {
                "mesh_ref": row["mesh_ref"],
                "mesh_url": f"/static/meshes/{row['mesh_ref']}" if row["mesh_ref"] else None,
                "centroid": [row["centroid_x"], row["centroid_y"], row["centroid_z"]]
                if row["centroid_x"] is not None
                else None,
                "bbox": self._bbox(row),
                "triangles": row["triangles"],
                "path": json.loads(row["path"]) if row["path"] else [],
            },
        }

    def relations(self, structure_id: str) -> dict[str, list[dict[str, Any]]]:
        """Outgoing relations grouped by predicate, each target labelled.

        A relation's object may be a structure outside the MSK subset (e.g. an innervating
        nerve, or a regional grouping FMA classifies outside our roots) that only has a display
        label, not a full page; ``resolvable`` tells the frontend whether it's safe to link to.
        """
        ids = self.structure_ids()
        out: dict[str, list[dict[str, Any]]] = {}
        for r in self._rows(
            "SELECT predicate, object, source FROM relations WHERE subject=? "
            "ORDER BY predicate, object",
            (structure_id,),
        ):
            out.setdefault(r["predicate"], []).append(
                {
                    "id": r["object"],
                    "name": self.label(r["object"]),
                    "source": r["source"],
                    "resolvable": r["object"] in ids,
                }
            )
        return out

    def incoming(self, structure_id: str) -> dict[str, list[dict[str, Any]]]:
        """Structures that point at this one (e.g. muscles originating on a bone)."""
        ids = self.structure_ids()
        out: dict[str, list[dict[str, Any]]] = {}
        for r in self._rows(
            "SELECT predicate, subject, source FROM relations WHERE object=? "
            "ORDER BY predicate, subject",
            (structure_id,),
        ):
            out.setdefault(r["predicate"], []).append(
                {
                    "id": r["subject"],
                    "name": self.label(r["subject"]),
                    "source": r["source"],
                    "resolvable": r["subject"] in ids,
                }
            )
        return out

    def list_structures(self, type_: str | None, with_mesh: bool) -> list[dict[str, Any]]:
        sql = "SELECT * FROM structures"
        clauses, params = [], []
        if type_:
            clauses.append("type=?")
            params.append(type_)
        if with_mesh:
            clauses.append("mesh_ref IS NOT NULL")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return [
            {
                "id": r["id"],
                "type": r["type"],
                "name": r["preferred"],
                "mesh_url": f"/static/meshes/{r['mesh_ref']}" if r["mesh_ref"] else None,
                "centroid": [r["centroid_x"], r["centroid_y"], r["centroid_z"]]
                if r["centroid_x"] is not None
                else None,
                "bbox": self._bbox(r),
            }
            for r in self._rows(sql + " ORDER BY preferred", tuple(params))
        ]

    def hierarchy(self) -> list[dict[str, Any]]:
        """Every structure with one chosen ``part_of`` parent, for a navigation tree.

        FMA gives many structures several parents (regional and constitutional). The most
        specific one is chosen: the parent with the longest ancestor chain of its own.
        Parents outside the bundle are dropped so the tree is fully navigable.
        """
        rows = self._rows("SELECT id, type, preferred, mesh_ref FROM structures")
        known = {r["id"] for r in rows}
        parents: dict[str, list[str]] = {}
        for r in self._rows(
            "SELECT subject, object FROM relations WHERE predicate='part_of' ORDER BY object"
        ):
            if r["object"] in known and r["subject"] in known:
                parents.setdefault(r["subject"], []).append(r["object"])

        depth_cache: dict[str, int] = {}

        def depth(node: str, trail: frozenset[str] = frozenset()) -> int:
            if node in depth_cache:
                return depth_cache[node]
            if node in trail:
                return 0
            ps = parents.get(node, [])
            d = 1 + max((depth(p, trail | {node}) for p in ps), default=-1)
            depth_cache[node] = d
            return d

        out = []
        for r in rows:
            ps = parents.get(r["id"], [])
            parent = max(ps, key=lambda p: (depth(p), p)) if ps else None
            out.append(
                {
                    "id": r["id"],
                    "name": r["preferred"],
                    "type": r["type"],
                    "parent": parent,
                    "has_mesh": r["mesh_ref"] is not None,
                }
            )
        return out

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        tokens = [t for t in query.replace('"', " ").split() if t]
        if not tokens:
            return []
        match = " ".join(f'"{t}"*' for t in tokens)
        rows = self._rows(
            """
            SELECT f.structure_id, f.name AS matched, f.kind, s.type, s.preferred,
                   s.centroid_x, s.centroid_y, s.centroid_z, s.mesh_ref
            FROM structures_fts f JOIN structures s ON s.id = f.structure_id
            WHERE structures_fts MATCH ?
            ORDER BY bm25(structures_fts), s.preferred
            LIMIT ?
            """,
            (match, limit * 3),
        )
        seen: set[str] = set()
        out = []
        for r in rows:
            if r["structure_id"] in seen:
                continue
            seen.add(r["structure_id"])
            out.append(
                {
                    "id": r["structure_id"],
                    "name": r["preferred"],
                    "type": r["type"],
                    "matched": r["matched"],
                    "matched_kind": r["kind"],
                    "has_mesh": r["mesh_ref"] is not None,
                    "centroid": [r["centroid_x"], r["centroid_y"], r["centroid_z"]]
                    if r["centroid_x"] is not None
                    else None,
                }
            )
            if len(out) >= limit:
                break
        return out

    # -- exercises ------------------------------------------------------------------------
    @staticmethod
    def _exercise(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "source": row["source"],
            "type": row["type"],
            "level": row["level"],
            "mechanic": row["mechanic"],
            "equipment": json.loads(row["equipment"]),
            "instructions": json.loads(row["instructions"]),
            "images": json.loads(row["images"]),
            "groups": json.loads(row["groups"]),
            "notes": row["notes"],
        }

    def exercise(self, exercise_id: str) -> dict[str, Any] | None:
        row = self.con.execute("SELECT * FROM exercises WHERE id=?", (exercise_id,)).fetchone()
        if row is None:
            return None
        ex = self._exercise(row)
        ex["structures"] = [
            {"id": r["structure_id"], "name": self.label(r["structure_id"]), "role": r["role"]}
            for r in self._rows(
                "SELECT structure_id, role FROM exercise_structures WHERE exercise_id=? "
                "ORDER BY role='secondary', structure_id",
                (exercise_id,),
            )
        ]
        return ex

    def exercises(
        self,
        structure_id: str | None,
        type_: str | None,
        equipment: str | None,
        level: str | None,
        role: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses, params = [], []
        sql_from = "FROM exercises e"
        if structure_id:
            sql_from += " JOIN exercise_structures es ON es.exercise_id = e.id"
            clauses.append("es.structure_id=?")
            params.append(structure_id)
            if role:
                clauses.append("es.role=?")
                params.append(role)
        if type_:
            clauses.append("e.type=?")
            params.append(type_)
        if level:
            clauses.append("e.level=?")
            params.append(level)
        if equipment:
            clauses.append("EXISTS (SELECT 1 FROM json_each(e.equipment) WHERE value=?)")
            params.append(equipment)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        total = self.con.execute(
            f"SELECT count(DISTINCT e.id) {sql_from}{where}", tuple(params)
        ).fetchone()[0]
        rows = self._rows(
            f"SELECT DISTINCT e.* {sql_from}{where} ORDER BY e.name LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        items = [self._exercise(r) for r in rows]
        if structure_id:
            for item in items:
                r = self.con.execute(
                    "SELECT role FROM exercise_structures WHERE exercise_id=? AND structure_id=?",
                    (item["id"], structure_id),
                ).fetchone()
                item["role"] = r["role"] if r else None
        return items, total

    def exercise_filters(self) -> dict[str, list[str]]:
        return {
            "types": [r[0] for r in self._rows("SELECT DISTINCT type FROM exercises ORDER BY 1")],
            "levels": [
                r[0]
                for r in self._rows(
                    "SELECT DISTINCT level FROM exercises WHERE level IS NOT NULL ORDER BY 1"
                )
            ],
            "equipment": [
                r[0]
                for r in self._rows(
                    "SELECT DISTINCT value FROM exercises, json_each(exercises.equipment) "
                    "ORDER BY 1"
                )
            ],
        }
