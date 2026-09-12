"""Orchestrate the build: parse -> enrich -> meshes -> exercises -> validate -> emit (§7)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from pipeline import bodyparts3d, fma, mapping, uberon, wikidata
from pipeline import exercises as ex
from pipeline.bundle import write_bundle
from pipeline.config import BuildConfig
from pipeline.content import load_content, validate_references
from pipeline.schemas import Attributed, Geometry, Names, Relation, Structure

log = logging.getLogger(__name__)


class BuildError(Exception):
    pass


@dataclass
class BuildReport:
    structures: int = 0
    with_mesh: int = 0
    relations: int = 0
    exercises: int = 0
    pain_patterns: int = 0
    mobilizations: int = 0
    unresolved_joints: list[tuple[str, str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=1)


def _load_fma_subset(cfg: BuildConfig) -> fma.FmaSubset:
    cache = cfg.cache_dir / "fma_msk.json"
    if cache.exists() and cfg.fma_file is None:
        log.info("using cached FMA subset %s", cache)
        return fma.FmaSubset.from_json(json.loads(cache.read_text()))
    src = cfg.fma_file or cfg.raw_dir / "fma" / "fma.owl"
    if not src.exists():
        raise BuildError(f"FMA source not found: {src} (run `anatomy-build fetch --fma`)")
    subset = fma.extract_msk_subset(fma.load_graph(src), cfg.roots)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(subset.to_json()))
    return subset


def _load_uberon(cfg: BuildConfig) -> dict[str, dict]:
    cache = cfg.cache_dir / "uberon_by_fma.json"
    if cache.exists() and cfg.uberon_file is None:
        return json.loads(cache.read_text())
    src = cfg.uberon_file or cfg.raw_dir / "uberon" / "uberon.owl"
    if not src.exists():
        log.warning("Uberon source not found (%s); definitions will be empty", src)
        return {}
    data = uberon.load_uberon(src)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data))
    return data


def _load_wikidata(cfg: BuildConfig) -> dict[str, dict]:
    src = cfg.wikidata_file or cfg.cache_dir / "wikidata_by_fma.json"
    if not src.exists():
        return {}
    return wikidata.load_wikidata(src)


def _name_matches(structure: Structure, expected: str) -> bool:
    needle = expected.lower()
    haystack = [structure.names.preferred.lower(), *(s.lower() for s in structure.names.synonyms)]
    return any(needle in h for h in haystack)


def validate_mapping(
    groups: mapping.MuscleGroupMapping, structures: dict[str, Structure]
) -> list[str]:
    problems: list[str] = []
    for group, entries in groups.groups.items():
        for e in entries:
            s = structures.get(e.id)
            if s is None:
                problems.append(f"muscle_groups[{group}]: {e.id} not in FMA MSK subset")
            elif not _name_matches(s, e.expect_name):
                problems.append(
                    f"muscle_groups[{group}]: {e.id} is {s.names.preferred!r} in FMA, "
                    f"expected {e.expect_name!r}"
                )
    return problems


def build(cfg: BuildConfig, *, write: bool = True) -> BuildReport:
    report = BuildReport()

    # 1. Semantics
    subset = _load_fma_subset(cfg)
    structures = subset.structures
    labels = dict(subset.labels)

    for ax_id, spec in mapping.load_local_ids(cfg.mapping_dir / "local_ids.yaml").items():
        structures[ax_id] = Structure(
            id=ax_id,
            type=spec["type"],
            names=Names(preferred=spec["name"], synonyms=spec.get("synonyms", [])),
        )
        labels[ax_id] = spec["name"]

    uberon_idx = _load_uberon(cfg)
    wd_idx = _load_wikidata(cfg)
    for s in structures.values():
        u = uberon_idx.get(s.id)
        if u:
            s.definition = uberon.definition_for(u)
            s.names.synonyms = sorted(set(s.names.synonyms) | set(u.get("synonyms", [])))
        w = wd_idx.get(s.id)
        if w:
            s.actions.extend(wikidata.actions_for(w))
            if w.get("description") and not s.definition:
                s.definition = Attributed(
                    text=w["description"], source=f"Wikidata {w['qid']}", license="CC0"
                )

    # 2. Mapping tables (validated against the FMA import)
    groups = mapping.load_muscle_groups(cfg.mapping_dir / "muscle_groups.yaml")
    report.errors += validate_mapping(groups, structures)
    authored = mapping.load_authored_relations(cfg.mapping_dir / "relations.yaml")
    joints = mapping.load_joints(cfg.mapping_dir / "joints.yaml")
    for r in authored:
        for end in (r.subject, r.object):
            if end not in structures:
                report.errors.append(f"relations.yaml: {end} not in FMA MSK subset")
    for pair, joint in joints.items():
        if joint not in structures:
            report.errors.append(f"joints.yaml: joint {joint} not in FMA MSK subset")
        for bone in pair:
            if bone not in structures:
                report.errors.append(f"joints.yaml: bone {bone} not in FMA MSK subset")

    # 3. Relations
    derived, unresolved = fma.derive_crosses_joint(subset, joints)
    report.unresolved_joints = unresolved
    relations: list[Relation] = [*subset.relations, *authored, *derived]

    # 4. Geometry
    if not cfg.skip_meshes:
        obj_dir = cfg.bodyparts3d_dir or cfg.raw_dir / "bodyparts3d" / "obj"
        if not obj_dir.exists():
            report.warnings.append(f"BodyParts3D directory not found: {obj_dir}; no meshes")
        else:
            element_parts_path = (
                cfg.bodyparts3d_element_parts_file
                or cfg.raw_dir / "bodyparts3d" / "isa_element_parts.txt"
            )
            infos = bodyparts3d.convert_all(
                obj_dir, set(structures), cfg.meshes_dir, cfg.max_triangles, element_parts_path
            )
            for fma_id, info in infos.items():
                structures[fma_id].geometry = Geometry(
                    mesh_ref=info.mesh_ref, centroid=info.centroid, triangles=info.triangles
                )
    report.with_mesh = sum(1 for s in structures.values() if s.geometry.mesh_ref)

    # 5. Exercises
    ex_file = cfg.exercises_file or cfg.raw_dir / "free-exercise-db" / "exercises.json"
    exercises = []
    if ex_file.exists():
        try:
            exercises = ex.convert_all(
                ex.load_free_exercise_db(ex_file), groups, cfg.sources.free_exercise_images
            )
        except ValueError as e:
            report.errors.append(str(e))
    else:
        report.warnings.append(f"exercise source not found: {ex_file}; no exercises")

    # 6. Authored content
    cs = load_content(cfg.content_dir)
    report.errors += cs.errors
    report.errors += validate_references(cs, set(structures))
    report.pain_patterns, report.mobilizations = len(cs.pain_patterns), len(cs.mobilizations)

    report.structures, report.relations, report.exercises = (
        len(structures),
        len(relations),
        len(exercises),
    )
    if report.errors:
        return report
    if write:
        write_bundle(
            cfg.db_path,
            structures,
            relations,
            exercises,
            labels,
            meta={
                "schema_version": "1",
                "sources": "FMA (CC BY 3.0), Uberon (CC BY 3.0), BodyParts3D (CC BY 4.0), "
                "free-exercise-db (public domain), Wikidata (CC0)",
            },
        )
        (cfg.bundle_dir / "build_report.json").write_text(report.to_json())
    return report
