"""BodyParts3D: part list + OBJ meshes keyed by FMA ID -> decimated GLB per structure.

The BodyParts3D archive ships ``*.obj`` files named by FMA ID (``FMA7163.obj``) plus a
tab-separated part list whose first column is the FMA ID and second the name. Column headers
vary between releases, so the parser keys on the ``FMA<digits>`` pattern rather than headers.
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


def convert_mesh(fma_id: str, obj_path: Path, out_dir: Path, max_triangles: int) -> MeshInfo | None:
    loaded = trimesh.load(str(obj_path), force="mesh", process=True)
    if not isinstance(loaded, trimesh.Trimesh) or loaded.is_empty:
        log.warning("%s: empty or unsupported mesh %s", fma_id, obj_path)
        return None
    mesh = _decimate(loaded, max_triangles)
    # BodyParts3D is in millimetres with the body's origin near the pelvis; glTF is metres.
    mesh.apply_scale(0.001)
    centroid = tuple(float(x) for x in np.asarray(mesh.bounding_box.centroid))
    rel = f"{fma_id.replace(':', '')}.glb"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Vertex normals are required for lit rendering; without them three.js produces NaN lighting.
    mesh.export(str(out_dir / rel), file_type="glb", include_normals=True)
    return MeshInfo(fma_id=fma_id, mesh_ref=rel, centroid=centroid, triangles=len(mesh.faces))


def convert_all(
    obj_dir: Path, wanted: set[str], out_dir: Path, max_triangles: int
) -> dict[str, MeshInfo]:
    files = find_obj_files(obj_dir)
    out: dict[str, MeshInfo] = {}
    missing = sorted(wanted - files.keys())
    if missing:
        log.info("%d wanted structures have no BodyParts3D mesh", len(missing))
    for fma_id in sorted(wanted & files.keys()):
        info = convert_mesh(fma_id, files[fma_id], out_dir, max_triangles)
        if info:
            out[fma_id] = info
    log.info("converted %d meshes", len(out))
    return out
