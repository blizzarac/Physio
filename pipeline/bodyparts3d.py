"""BodyParts3D: part list + OBJ meshes keyed by FMA ID -> decimated GLB per structure.

Some BodyParts3D releases ship ``*.obj`` files named by FMA ID (``FMA7163.obj``) plus a
tab-separated part list whose first column is the FMA ID and second the name; the parser keys
on the ``FMA<digits>`` pattern rather than headers since column headers vary between releases.

The current ISA-hierarchy release instead names OBJs by an internal "element file ID"
(``FJ1813.obj``), unrelated to the FMA ID. ``isa_element_parts.txt`` maps each FMA concept ID
to one or more element file IDs; a compound structure's mesh is the union of its elements'
meshes. ``convert_all`` tries the direct FMA-named lookup first (fixtures, older releases) and
falls back to the element-parts mapping when an ``element_parts_path`` is given.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh

from pipeline.ids import normalize_fma

log = logging.getLogger(__name__)

_FMA_COL = re.compile(r"^FMA\d+$")


@dataclass
class MeshInfo:
    fma_id: str
    mesh_ref: str  # path relative to the bundle's static/meshes directory
    centroid: tuple[float, float, float]
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    triangles: int


def read_part_list(path: Path) -> dict[str, str]:
    """Return {FMA ID: BodyParts3D name} from any BP3D part-list TSV."""
    out: dict[str, str] = {}
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 2 or not _FMA_COL.match(cols[0].strip()):
                continue
            out[normalize_fma(cols[0])] = cols[1].strip()
    return out


def find_obj_files(obj_dir: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in obj_dir.rglob("*.obj"):
        stem = p.stem
        if _FMA_COL.match(stem):
            out[normalize_fma(stem)] = p
    return out


def read_element_parts(path: Path) -> dict[str, list[str]]:
    """Return {FMA ID: [element file ID, ...]} from ``isa_element_parts.txt``."""
    out: dict[str, list[str]] = {}
    with path.open(encoding="utf-8", errors="replace") as fh:
        next(fh, None)  # header
        for line in fh:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 3 or not _FMA_COL.match(cols[0].strip()):
                continue
            out.setdefault(normalize_fma(cols[0]), []).append(cols[2].strip())
    return out


def _index_by_stem(obj_dir: Path) -> dict[str, Path]:
    return {p.stem: p for p in obj_dir.rglob("*.obj")}


def _decimate(mesh: trimesh.Trimesh, max_triangles: int) -> trimesh.Trimesh:
    if len(mesh.faces) <= max_triangles:
        return mesh
    try:
        import fast_simplification  # noqa: F401  (optional extra "mesh")
    except ImportError:
        log.warning(
            "mesh has %d faces > %d but fast_simplification is not installed; "
            "install '.[mesh]' to decimate",
            len(mesh.faces),
            max_triangles,
        )
        return mesh
    return mesh.simplify_quadric_decimation(face_count=max_triangles)


def convert_mesh(
    fma_id: str, obj_paths: Path | list[Path], out_dir: Path, max_triangles: int
) -> MeshInfo | None:
    paths = [obj_paths] if isinstance(obj_paths, Path) else obj_paths
    loaded_parts = []
    for obj_path in paths:
        loaded = trimesh.load(str(obj_path), force="mesh", process=True)
        if isinstance(loaded, trimesh.Trimesh) and not loaded.is_empty:
            loaded_parts.append(loaded)
    if not loaded_parts:
        log.warning("%s: empty or unsupported mesh(es) %s", fma_id, paths)
        return None
    loaded = loaded_parts[0] if len(loaded_parts) == 1 else trimesh.util.concatenate(loaded_parts)
    mesh = _decimate(loaded, max_triangles)
    # BodyParts3D is in millimetres, Z-up (superior = +Z, anterior = -Y). glTF is metres, Y-up
    # with the viewer looking down -Z, so rotate -90° about X: (x, y, z) -> (x, z, -y).
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, (1, 0, 0)))
    mesh.apply_scale(0.001)
    centroid = tuple(float(x) for x in np.asarray(mesh.bounding_box.centroid))
    bmin, bmax = (tuple(float(x) for x in row) for row in np.asarray(mesh.bounds))
    rel = f"{fma_id.replace(':', '')}.glb"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Vertex normals are required for lit rendering; without them three.js produces NaN lighting.
    mesh.export(str(out_dir / rel), file_type="glb", include_normals=True)
    return MeshInfo(
        fma_id=fma_id,
        mesh_ref=rel,
        centroid=centroid,
        bbox_min=bmin,
        bbox_max=bmax,
        triangles=len(mesh.faces),
    )


def convert_all(
    obj_dir: Path,
    wanted: set[str],
    out_dir: Path,
    max_triangles: int,
    element_parts_path: Path | None = None,
) -> dict[str, MeshInfo]:
    files = find_obj_files(obj_dir)
    out: dict[str, MeshInfo] = {}
    for fma_id in sorted(wanted & files.keys()):
        info = convert_mesh(fma_id, files[fma_id], out_dir, max_triangles)
        if info:
            out[fma_id] = info

    remaining = wanted - out.keys()
    if remaining and element_parts_path and element_parts_path.exists():
        by_stem = _index_by_stem(obj_dir)
        element_parts = read_element_parts(element_parts_path)
        for fma_id in sorted(remaining):
            element_ids = element_parts.get(fma_id)
            if not element_ids:
                continue
            paths = [by_stem[e] for e in element_ids if e in by_stem]
            if not paths:
                continue
            info = convert_mesh(fma_id, paths, out_dir, max_triangles)
            if info:
                out[fma_id] = info

    missing = sorted(wanted - out.keys())
    if missing:
        log.info("%d wanted structures have no BodyParts3D mesh", len(missing))
    log.info("converted %d meshes", len(out))
    return out
