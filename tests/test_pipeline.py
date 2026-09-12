from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from pipeline import fma
from pipeline.build import build
from pipeline.config import MskRoots
from pipeline.content import ContentError, load_content, parse_entry, validate_references
from pipeline.ids import normalize_fma, normalize_id
from tests.conftest import FIXTURES, make_config


def test_normalize_ids():
    assert normalize_fma("FMA:22356") == "FMA:22356"
    assert normalize_fma("FMA22356") == "FMA:22356"
    assert normalize_fma("fma22356") == "FMA:22356"
    assert normalize_fma("http://purl.org/sig/ont/fma/fma22356") == "FMA:22356"
    assert normalize_id("ax:some-thing") == "ax:some-thing"
    with pytest.raises(ValueError):
        normalize_fma("UBERON:0001374")


def test_fma_subset_extraction():
    g = fma.load_graph(FIXTURES / "fma_mini.ttl")
    subset = fma.extract_msk_subset(g, MskRoots())
    bf = subset.structures["FMA:22356"]
    assert bf.type == "muscle"
    assert bf.names.preferred == "Biceps femoris"
    assert "Biceps femoris muscle" in bf.names.synonyms
    assert bf.ta2 == "A04.7.02.032"
    assert subset.structures["FMA:24474"].type == "bone"
    assert subset.structures["FMA:24964"].type == "joint"
    preds = {(r.predicate, r.object) for r in subset.relations if r.subject == "FMA:22356"}
    assert ("origin", "FMA:16580") in preds
    assert ("insertion", "FMA:24477") in preds
    assert ("innervation", "FMA:19035") in preds
    assert ("part_of", "FMA:9001") in preds
    # nerve is outside the roots but still gets a label
    assert subset.labels["FMA:19035"] == "Tibial nerve"
    assert "FMA:19035" not in subset.structures
    # regional chain walked upward: compartment -> thigh -> lower limb -> body
    for rid, name in [
        ("FMA:45959", "Posterior compartment of thigh"),
        ("FMA:24966", "Thigh"),
        ("FMA:24875", "Lower limb"),
        ("FMA:20394", "Human body"),
    ]:
        assert (
            subset.structures[rid].type == "region"
            and subset.structures[rid].names.preferred == name
        )
    assert ("part_of", "FMA:45959") in preds
    assert ("FMA:45959", "part_of", "FMA:24966") in {
        (r.subject, r.predicate, r.object) for r in subset.relations
    }


def test_wrong_root_name_is_rejected():
    g = fma.load_graph(FIXTURES / "fma_mini.ttl")
    roots = MskRoots(muscle=("FMA:5022", "Nerve organ"))
    with pytest.raises(ValueError, match="expected 'Nerve organ'"):
        fma.extract_msk_subset(g, roots)


def test_full_build_writes_bundle(built_bundle):
    cfg = built_bundle
    assert cfg.db_path.exists()
    glb = (cfg.meshes_dir / "FMA22356.glb").read_bytes()
    assert b"NORMAL" in glb, "GLB must carry vertex normals for lit rendering"
    report = json.loads((cfg.bundle_dir / "build_report.json").read_text())
    assert report["with_mesh"] == 2
    assert report["exercises"] == 2
    assert report["pain_patterns"] == 1 and report["mobilizations"] == 1

    con = sqlite3.connect(cfg.db_path)
    row = con.execute(
        "SELECT type, preferred, definition, mesh_ref, triangles FROM structures WHERE id='FMA:22356'"
    ).fetchone()
    assert row[0] == "muscle" and row[1] == "Biceps femoris"
    assert "hamstring" in json.loads(row[2])["text"]
    assert row[3] == "FMA22356.glb" and row[4] == 12
    bbox = con.execute(
        "SELECT bbox_min_x, bbox_max_x, bbox_min_y, bbox_max_y FROM structures WHERE id='FMA:22356'"
    ).fetchone()
    assert bbox[0] == pytest.approx(-0.05) and bbox[1] == pytest.approx(0.05)
    assert bbox[3] - bbox[2] == pytest.approx(0.04)
    # uberon synonym merged into the names table
    assert con.execute(
        "SELECT 1 FROM names WHERE structure_id='FMA:22356' AND name='musculus biceps femoris'"
    ).fetchone()
    # derived crosses_joint: hip bone -> tibia has no joint entry, so biceps femoris resolves none
    # but gluteus maximus (hip bone -> femur) crosses the hip joint.
    assert con.execute(
        "SELECT 1 FROM relations WHERE subject='FMA:22314' AND predicate='crosses_joint' "
        "AND object='FMA:24964'"
    ).fetchone()
    assert ["FMA:22356", "FMA:16580", "FMA:24477"] in report["unresolved_joints"]
    # authored relations are symmetric
    assert (
        con.execute("SELECT count(*) FROM relations WHERE predicate='antagonist_of'").fetchone()[0]
        == 2
    )
    # exercises mapped to FMA IDs
    rows = con.execute(
        "SELECT structure_id, role FROM exercise_structures WHERE exercise_id='fedb:Romanian_Deadlift' "
        "ORDER BY role, structure_id"
    ).fetchall()
    assert ("FMA:22356", "primary") in rows and ("FMA:22314", "secondary") in rows
    assert (
        con.execute(
            "SELECT type FROM exercises WHERE id='fedb:Upper_Trapezius_Stretch'"
        ).fetchone()[0]
        == "stretch"
    )
    # FTS search works with diacritics-insensitive tokenizer
    hit = con.execute(
        "SELECT structure_id FROM structures_fts WHERE structures_fts MATCH 'trapez*'"
    ).fetchone()
    assert hit[0] == "FMA:9626"
    # local ax: id present
    assert (
        con.execute("SELECT type FROM structures WHERE id='ax:test-fascia'").fetchone()[0]
        == "fascia"
    )
    con.close()


def test_mapping_name_mismatch_fails_build(tmp_path: Path, bp3d_dir: Path):
    mapping_dir = tmp_path / "mapping"
    mapping_dir.mkdir()
    (mapping_dir / "muscle_groups.yaml").write_text(
        'hamstrings:\n  - { id: "FMA:22356", expect_name: "gluteus maximus" }\n'
        'glutes:\n  - { id: "FMA:99999", expect_name: "x" }\n'
        'lower back:\n  - { id: "FMA:22315", expect_name: "gluteus medius" }\n'
        'traps:\n  - { id: "FMA:9626", expect_name: "trapezius" }\n'
    )
    cfg = make_config(tmp_path, bp3d_dir, mapping_dir=mapping_dir, skip_meshes=True)
    report = build(cfg)
    assert any("expected 'gluteus maximus'" in e for e in report.errors)
    assert any("FMA:99999 not in FMA MSK subset" in e for e in report.errors)
    assert not cfg.db_path.exists()


def test_unmapped_exercise_group_is_reported(tmp_path: Path, bp3d_dir: Path):
    ex_file = tmp_path / "ex.json"
    ex_file.write_text(
        json.dumps(
            [{"id": "X", "name": "X", "primaryMuscles": ["forearms"], "category": "strength"}]
        )
    )
    cfg = make_config(tmp_path, bp3d_dir, exercises_file=ex_file, skip_meshes=True)
    report = build(cfg)
    assert any("forearms" in e for e in report.errors)


def test_content_parsing_and_validation(content_copy: Path):
    entry = parse_entry(content_copy / "pain" / "upper-trapezius-trigger-point.md")
    assert entry.type == "pain_pattern" and entry.structure == "FMA:9626"
    assert entry.body.startswith("The most common trigger point")

    bad = content_copy / "pain" / "bad.md"
    bad.write_text(
        "---\ntype: pain_pattern\nid: pp-bad\nstructure: FMA:1\nkind: strain\n---\nno sources\n"
    )
    with pytest.raises(ContentError, match="sources"):
        parse_entry(bad)

    cs = load_content(content_copy)
    assert len(cs.errors) == 1 and "bad.md" in cs.errors[0]
    problems = validate_references(cs, {"FMA:9626", "FMA:22315", "FMA:22317", "FMA:24964"})
    assert len(problems) == 2  # the two referral regions of the trapezius entry
    assert all("references unknown structure" in p for p in problems)


def test_repo_content_and_mapping_parse():
    """The real content/ and mapping/ must at least be well-formed (IDs are checked at build)."""
    from pipeline.mapping import load_authored_relations, load_joints, load_muscle_groups

    cs = load_content(Path("content"))
    assert cs.errors == []
    assert len(cs.pain_patterns) >= 1 and len(cs.mobilizations) >= 1
    groups = load_muscle_groups(Path("mapping/muscle_groups.yaml"))
    fedb_groups = {
        "abdominals",
        "abductors",
        "adductors",
        "biceps",
        "calves",
        "chest",
        "forearms",
        "glutes",
        "hamstrings",
        "lats",
        "lower back",
        "middle back",
        "neck",
        "quadriceps",
        "shoulders",
        "traps",
        "triceps",
    }
    assert fedb_groups <= set(groups.groups)
    assert load_authored_relations(Path("mapping/relations.yaml"))
    assert load_joints(Path("mapping/joints.yaml"))
