"""Write the data bundle: one SQLite file (+ FTS5) and a directory of GLB meshes (§7)."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pipeline.schemas import Exercise, Relation, Structure

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE structures (
    id            TEXT PRIMARY KEY,
    type          TEXT NOT NULL,
    preferred     TEXT NOT NULL,
    latin         TEXT,
    ta2           TEXT,
    definition    TEXT,           -- JSON Attributed or NULL
    actions       TEXT NOT NULL,  -- JSON list of Attributed
    mesh_ref      TEXT,
    centroid_x    REAL, centroid_y REAL, centroid_z REAL,
    triangles     INTEGER,
    path          TEXT            -- JSON list of [x,y,z] or NULL
);

CREATE TABLE names (
    structure_id TEXT NOT NULL REFERENCES structures(id),
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL   -- preferred | latin | synonym
);
CREATE INDEX names_structure ON names(structure_id);

-- Labels for structures referenced by relations but outside the MSK subset (nerves, arteries).
CREATE TABLE labels (id TEXT PRIMARY KEY, name TEXT NOT NULL);

CREATE TABLE relations (
    subject   TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object    TEXT NOT NULL,
    source    TEXT NOT NULL,
    PRIMARY KEY (subject, predicate, object)
);
CREATE INDEX relations_object ON relations(object, predicate);

CREATE TABLE exercises (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    source       TEXT NOT NULL,
    type         TEXT NOT NULL,
    level        TEXT,
    mechanic     TEXT,
    equipment    TEXT NOT NULL,   -- JSON list
    instructions TEXT NOT NULL,   -- JSON list
    images       TEXT NOT NULL,   -- JSON list
    groups       TEXT NOT NULL,   -- JSON {primary: [], secondary: []}
    notes        TEXT
);

CREATE TABLE exercise_structures (
    exercise_id  TEXT NOT NULL REFERENCES exercises(id),
    structure_id TEXT NOT NULL,
    role         TEXT NOT NULL,   -- primary | secondary
    PRIMARY KEY (exercise_id, structure_id, role)
);
CREATE INDEX exercise_structures_structure ON exercise_structures(structure_id);

CREATE VIRTUAL TABLE structures_fts USING fts5(
    structure_id UNINDEXED, name, kind UNINDEXED, tokenize = 'unicode61 remove_diacritics 2'
);
"""


def write_bundle(
    db_path: Path,
    structures: dict[str, Structure],
    relations: list[Relation],
    exercises: list[Exercise],
    labels: dict[str, str],
    meta: dict[str, str],
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    try:
        con.executescript(SCHEMA)
        con.executemany(
            "INSERT INTO meta VALUES (?, ?)",
            [*meta.items(), ("built_at", datetime.now(UTC).isoformat(timespec="seconds"))],
        )
        for s in structures.values():
            g = s.geometry
            cx, cy, cz = g.centroid if g.centroid else (None, None, None)
            con.execute(
                "INSERT INTO structures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    s.id,
                    s.type,
                    s.names.preferred,
                    s.names.latin,
                    s.ta2,
                    json.dumps(s.definition.model_dump()) if s.definition else None,
                    json.dumps([a.model_dump() for a in s.actions]),
                    g.mesh_ref,
                    cx,
                    cy,
                    cz,
                    g.triangles,
                    json.dumps(g.path) if g.path else None,
                ),
            )
            rows = [(s.id, s.names.preferred, "preferred")]
            if s.names.latin:
                rows.append((s.id, s.names.latin, "latin"))
            rows += [(s.id, syn, "synonym") for syn in s.names.synonyms]
            con.executemany("INSERT INTO names VALUES (?,?,?)", rows)
            con.executemany("INSERT INTO structures_fts VALUES (?,?,?)", rows)
        con.executemany(
            "INSERT INTO labels VALUES (?,?)",
            [(k, v) for k, v in labels.items() if k not in structures],
        )
        con.executemany(
            "INSERT OR IGNORE INTO relations VALUES (?,?,?,?)",
            [(r.subject, r.predicate, r.object, r.source) for r in relations],
        )
        for e in exercises:
            con.execute(
                "INSERT INTO exercises VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    e.id,
                    e.name,
                    e.source,
                    e.type,
                    e.level,
                    e.mechanic,
                    json.dumps(e.equipment),
                    json.dumps(e.instructions),
                    json.dumps(e.images),
                    json.dumps({"primary": e.primary_groups, "secondary": e.secondary_groups}),
                    e.notes,
                ),
            )
            con.executemany(
                "INSERT OR IGNORE INTO exercise_structures VALUES (?,?,?)",
                [(e.id, s, "primary") for s in e.primary_structures]
                + [(e.id, s, "secondary") for s in e.secondary_structures],
            )
        con.commit()
    finally:
        con.close()
    log.info(
        "bundle written: %s (%d structures, %d relations, %d exercises)",
        db_path,
        len(structures),
        len(relations),
        len(exercises),
    )
