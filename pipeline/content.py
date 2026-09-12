"""Load authored Markdown + YAML frontmatter content (design doc §9).

Each file has a ``type`` in its frontmatter (``pain_pattern`` or ``mobilization``); the body
below the frontmatter is the free-text description rendered by the UI.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from pipeline.schemas import Mobilization, PainPattern

log = logging.getLogger(__name__)

_MODELS = {"pain_pattern": PainPattern, "mobilization": Mobilization}


class ContentError(ValueError):
    pass


_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ContentError("file does not start with a YAML frontmatter block ('---')")
    m = _FRONTMATTER_RE.match(text)
    if m is None:
        raise ContentError("unterminated frontmatter block")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ContentError("frontmatter must be a mapping")
    return meta, text[m.end() :].strip("\n")


def parse_entry(path: Path) -> PainPattern | Mobilization:
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    kind = meta.get("type")
    model = _MODELS.get(kind)
    if model is None:
        raise ContentError(f"{path}: unknown or missing content type {kind!r}")
    try:
        return model.model_validate({**meta, "body": body, "file": str(path)})
    except ValidationError as e:
        raise ContentError(f"{path}: {e}") from e


@dataclass
class ContentSet:
    pain_patterns: list[PainPattern] = field(default_factory=list)
    mobilizations: list[Mobilization] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def all_entries(self):
        return [*self.pain_patterns, *self.mobilizations]


def load_content(content_dir: Path) -> ContentSet:
    cs = ContentSet()
    ids: dict[str, Path] = {}
    # Entries live in subdirectories (pain/, mobilization/); top-level files such as README.md
    # and disclaimer.md are documentation, not entries.
    for path in sorted(content_dir.rglob("*.md")):
        if path.parent == content_dir:
            continue
        try:
            entry = parse_entry(path)
        except ContentError as e:
            cs.errors.append(str(e))
            continue
        if entry.id in ids:
            cs.errors.append(f"{path}: duplicate id {entry.id!r} (also in {ids[entry.id]})")
            continue
        ids[entry.id] = path
        if isinstance(entry, PainPattern):
            cs.pain_patterns.append(entry)
        else:
            cs.mobilizations.append(entry)
    log.info(
        "content: %d pain patterns, %d mobilizations, %d errors",
        len(cs.pain_patterns),
        len(cs.mobilizations),
        len(cs.errors),
    )
    return cs


def validate_references(cs: ContentSet, known_ids: set[str]) -> list[str]:
    """Every FMA/ax ID referenced by content must exist in the built structure set."""
    problems: list[str] = []
    for entry in cs.all_entries():
        for ref in entry.referenced_ids():
            if ref not in known_ids:
                problems.append(f"{entry.file}: references unknown structure {ref}")
    return problems
