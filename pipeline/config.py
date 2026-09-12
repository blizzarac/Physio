"""Build configuration: source locations, MSK subset roots, output paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class SourceUrls:
    # FMA is distributed via BioPortal (needs a free API key) or as a local file.
    fma_owl: str = (
        "https://data.bioontology.org/ontologies/FMA/download?apikey=${BIOPORTAL_API_KEY}"
    )
    uberon_owl: str = "http://purl.obolibrary.org/obo/uberon.owl"
    free_exercise_db: str = (
        "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/dist/exercises.json"
    )
    free_exercise_images: str = (
        "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/"
    )
    bodyparts3d_obj: str = (
        "https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/isa_BP3D_4.0_obj_99.zip"
    )
    # Maps FMA concept ID -> element file ID(s); the OBJ files in bodyparts3d_obj are named by
    # element file ID (e.g. FJ1813.obj), not FMA ID, and a compound structure can be made of
    # several element files that must be merged into one mesh.
    bodyparts3d_element_parts: str = (
        "https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/isa_element_parts.txt"
    )
    wikidata_sparql: str = "https://query.wikidata.org/sparql"


@dataclass
class MskRoots:
    """FMA classes whose subclass trees define the musculoskeletal subset.

    Each root is (FMA ID, expected preferred name). The loader checks the name so a wrong root
    ID is caught immediately rather than producing an empty or nonsensical subset.
    """

    muscle: tuple[str, str] = ("FMA:5022", "Muscle organ")
    bone: tuple[str, str] = ("FMA:5018", "Bone organ")
    joint: tuple[str, str] = ("FMA:7490", "Joint")
    ligament: tuple[str, str] = ("FMA:21496", "Ligament organ")
    tendon: tuple[str, str] = ("FMA:9721", "Tendon")
    fascia: tuple[str, str] = ("FMA:321912", "Fascia")

    def items(self):
        return [(name, fma_id, expected) for name, (fma_id, expected) in self.__dict__.items()]


@dataclass
class BuildConfig:
    raw_dir: Path = REPO_ROOT / "data" / "raw"
    cache_dir: Path = REPO_ROOT / "data" / "cache"
    bundle_dir: Path = REPO_ROOT / "data" / "bundle"
    content_dir: Path = REPO_ROOT / "content"
    mapping_dir: Path = REPO_ROOT / "mapping"
    max_triangles: int = 20_000
    sources: SourceUrls = field(default_factory=SourceUrls)
    roots: MskRoots = field(default_factory=MskRoots)
    # Optional overrides for local source files (used by tests and offline builds).
    fma_file: Path | None = None
    uberon_file: Path | None = None
    exercises_file: Path | None = None
    bodyparts3d_dir: Path | None = None
    bodyparts3d_element_parts_file: Path | None = None
    wikidata_file: Path | None = None
    skip_meshes: bool = False

    @property
    def db_path(self) -> Path:
        return self.bundle_dir / "anatomy.sqlite"

    @property
    def meshes_dir(self) -> Path:
        return self.bundle_dir / "static" / "meshes"

    @classmethod
    def from_yaml(cls, path: Path) -> BuildConfig:
        data = yaml.safe_load(path.read_text()) or {}
        cfg = cls()
        for key, value in data.items():
            if not hasattr(cfg, key):
                raise KeyError(f"unknown config key {key!r} in {path}")
            current = getattr(cfg, key)
            if isinstance(current, Path) or key.endswith(("_file", "_dir")):
                value = Path(value) if value is not None else None
            setattr(cfg, key, value)
        return cfg
