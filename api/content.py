"""Authored content store with hot reload (design doc §7, §9).

The content directory is parsed with the same loader the build uses. A background thread
watches the directory (``watchfiles``) and swaps in a fresh snapshot on any change; invalid
files are reported in ``/content/status`` and skipped rather than taking the API down.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from pipeline.content import ContentSet, load_content, validate_references

log = logging.getLogger(__name__)


@dataclass
class Snapshot:
    content: ContentSet
    sources: dict[str, dict[str, Any]]
    disclaimer: str
    reference_errors: list[str] = field(default_factory=list)


class ContentStore:
    def __init__(self, content_dir: Path, known_ids: set[str]):
        self.content_dir = content_dir
        self.known_ids = known_ids
        self._snapshot = self._load()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- loading ---------------------------------------------------------------------------
    def _load(self) -> Snapshot:
        cs = load_content(self.content_dir) if self.content_dir.exists() else ContentSet()
        ref_errors = validate_references(cs, self.known_ids)
        sources_file = self.content_dir / "sources.yaml"
        sources = yaml.safe_load(sources_file.read_text()) if sources_file.exists() else {}
        disclaimer_file = self.content_dir / "disclaimer.md"
        disclaimer = disclaimer_file.read_text().strip() if disclaimer_file.exists() else ""
        if cs.errors or ref_errors:
            for e in [*cs.errors, *ref_errors]:
                log.warning("content: %s", e)
        return Snapshot(cs, sources or {}, disclaimer, ref_errors)

    def reload(self) -> None:
        self._snapshot = self._load()
        log.info("content reloaded from %s", self.content_dir)

    def start_watching(self) -> None:
        try:
            from watchfiles import watch
        except ImportError:  # pragma: no cover
            log.warning("watchfiles not installed; content hot reload disabled")
            return

        def run() -> None:
            for _changes in watch(self.content_dir, stop_event=self._stop):
                try:
                    self.reload()
                except Exception:  # noqa: BLE001 - keep serving the last good snapshot
                    log.exception("content reload failed")

        self._thread = threading.Thread(target=run, name="content-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # -- queries ---------------------------------------------------------------------------
    @property
    def snapshot(self) -> Snapshot:
        return self._snapshot

    def _entry(self, entry, label) -> dict[str, Any]:
        data = entry.model_dump(exclude={"file"})
        data["sources"] = [
            {"id": s, **self._snapshot.sources.get(s, {"title": s})} for s in entry.sources
        ]
        return self._label_ids(data, label)

    @staticmethod
    def _label_ids(data: dict[str, Any], label) -> dict[str, Any]:
        for key in ("structure", "joint"):
            if data.get(key):
                data[key] = {"id": data[key], "name": label(data[key])}
        for key in ("referral_regions", "targets"):
            if key in data:
                data[key] = [{"id": i, "name": label(i)} for i in data[key]]
        return data

    def pain_for(self, structure_id: str, label) -> list[dict[str, Any]]:
        return [
            self._entry(p, label)
            for p in self._snapshot.content.pain_patterns
            if p.structure == structure_id or structure_id in p.referral_regions
        ]

    def mobilizations_for(self, structure_id: str, label) -> list[dict[str, Any]]:
        return [
            self._entry(m, label)
            for m in self._snapshot.content.mobilizations
            if structure_id in m.targets or m.joint == structure_id
        ]

    def all_pain(self, label) -> list[dict[str, Any]]:
        return [self._entry(p, label) for p in self._snapshot.content.pain_patterns]

    def all_mobilizations(self, label) -> list[dict[str, Any]]:
        return [self._entry(m, label) for m in self._snapshot.content.mobilizations]

    def status(self) -> dict[str, Any]:
        s = self._snapshot
        return {
            "content_dir": str(self.content_dir),
            "pain_patterns": len(s.content.pain_patterns),
            "mobilizations": len(s.content.mobilizations),
            "parse_errors": s.content.errors,
            "reference_errors": s.reference_errors,
        }
