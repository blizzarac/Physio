"""Load the hand-curated mapping tables under mapping/ (design doc §6)."""

from __future__ import annotations

from pathlib import Path

import yaml

from pipeline.ids import normalize_id
from pipeline.schemas import MappingEntry, MuscleGroupMapping, Relation


def load_muscle_groups(path: Path) -> MuscleGroupMapping:
    data = yaml.safe_load(path.read_text()) or {}
    groups: dict[str, list[MappingEntry]] = {}
    for group, entries in data.items():
        groups[str(group).lower()] = [MappingEntry.model_validate(e) for e in entries or []]
    return MuscleGroupMapping(groups=groups)


def load_authored_relations(path: Path) -> list[Relation]:
    """mapping/relations.yaml: ``antagonist_of`` / ``synergist_of`` pairs.

    Format::

        antagonist_of:
          - [FMA:37670, FMA:37688]   # biceps brachii <-> triceps brachii
        synergist_of:
          - [FMA:22356, FMA:22357]

    Pairs are symmetric; both directions are emitted.
    """
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text()) or {}
    out: list[Relation] = []
    for predicate in ("antagonist_of", "synergist_of"):
        for pair in data.get(predicate, []) or []:
            if len(pair) != 2:
                raise ValueError(f"{path}: {predicate} entries must be pairs, got {pair!r}")
            a, b = normalize_id(pair[0]), normalize_id(pair[1])
            out.append(Relation(subject=a, predicate=predicate, object=b, source="authored"))
            out.append(Relation(subject=b, predicate=predicate, object=a, source="authored"))
    return out


def load_joints(path: Path) -> dict[frozenset[str], str]:
    """mapping/joints.yaml: bone pair -> joint FMA ID, used to resolve ``crosses_joint``."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    out: dict[frozenset[str], str] = {}
    for joint, bones in data.items():
        if len(bones) != 2:
            raise ValueError(f"{path}: {joint} must list exactly two bones")
        out[frozenset(normalize_id(b) for b in bones)] = normalize_id(joint)
    return out


def load_local_ids(path: Path) -> dict[str, dict]:
    """mapping/local_ids.yaml: ``ax:`` structures that have no FMA entry."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return {normalize_id(k): v for k, v in data.items()}
