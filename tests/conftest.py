from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import trimesh

from pipeline.build import build
from pipeline.config import BuildConfig

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def bp3d_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Fake BodyParts3D export: two OBJ boxes named by FMA ID plus a part list."""
    d = tmp_path_factory.mktemp("bp3d")
    trimesh.creation.box(extents=(100, 40, 40)).export(str(d / "FMA22356.obj"))
    trimesh.creation.box(extents=(300, 60, 60)).export(str(d / "FMA24474.obj"))
    (d / "isa_parts_list.txt").write_text(
        "FMAID\tBodyPart\nFMA22356\tbiceps femoris\nFMA24474\tfemur\n"
    )
    return d


def make_config(tmp: Path, bp3d_dir: Path, **overrides) -> BuildConfig:
    cfg = BuildConfig(
        raw_dir=tmp / "raw",
        cache_dir=tmp / "cache",
        bundle_dir=tmp / "bundle",
        content_dir=FIXTURES / "content",
        mapping_dir=FIXTURES / "mapping",
        fma_file=FIXTURES / "fma_mini.ttl",
        uberon_file=FIXTURES / "uberon_mini.ttl",
        exercises_file=FIXTURES / "exercises_mini.json",
        bodyparts3d_dir=bp3d_dir,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


@pytest.fixture(scope="session")
def built_bundle(tmp_path_factory: pytest.TempPathFactory, bp3d_dir: Path) -> BuildConfig:
    tmp = tmp_path_factory.mktemp("build")
    cfg = make_config(tmp, bp3d_dir)
    report = build(cfg)
    assert report.errors == [], report.errors
    return cfg


@pytest.fixture
def content_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "content"
    shutil.copytree(FIXTURES / "content", dest)
    return dest
