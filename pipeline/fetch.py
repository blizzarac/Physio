"""Download raw sources into data/raw. Every download is skipped if the target exists."""

from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path

import httpx

from pipeline.config import BuildConfig

log = logging.getLogger(__name__)


def _download(url: str, dest: Path, timeout: float = 600.0) -> Path:
    if dest.exists():
        log.info("exists, skipping: %s", dest)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    log.info("downloading %s -> %s", url.split("?")[0], dest)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_bytes(1 << 20):
                fh.write(chunk)
    tmp.rename(dest)
    return dest


def fetch_all(cfg: BuildConfig, *, fma: bool, uberon: bool, exercises: bool, bp3d: bool) -> None:
    raw = cfg.raw_dir
    if exercises:
        _download(cfg.sources.free_exercise_db, raw / "free-exercise-db" / "exercises.json")
    if uberon:
        _download(cfg.sources.uberon_owl, raw / "uberon" / "uberon.owl")
    if fma:
        url = os.path.expandvars(cfg.sources.fma_owl)
        if "${BIOPORTAL_API_KEY}" in url or "apikey=$" in url:
            raise SystemExit(
                "FMA download needs BIOPORTAL_API_KEY in the environment "
                "(free key from https://bioportal.bioontology.org/), or place fma.owl in "
                f"{raw / 'fma'} and pass --fma-file."
            )
        _download(url, raw / "fma" / "fma.owl")
    if bp3d:
        archive = _download(cfg.sources.bodyparts3d_obj, raw / "bodyparts3d" / "isa_obj.zip")
        target = raw / "bodyparts3d" / "obj"
        if not target.exists():
            log.info("extracting %s", archive)
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(target)
        _download(
            cfg.sources.bodyparts3d_element_parts,
            raw / "bodyparts3d" / "isa_element_parts.txt",
        )
