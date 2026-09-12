"""Import free-exercise-db (public domain) and map informal muscle groups to FMA IDs."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pipeline.schemas import Exercise, ExerciseType, MuscleGroupMapping

log = logging.getLogger(__name__)

_CATEGORY_TO_TYPE: dict[str, ExerciseType] = {
    "stretching": "stretch",
    "strength": "strength",
    "powerlifting": "strength",
    "strongman": "strength",
    "olympic weightlifting": "strength",
    "plyometrics": "strength",
    "cardio": "strength",
}


def load_free_exercise_db(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def convert_free_exercise(raw: dict, mapping: MuscleGroupMapping, image_base: str) -> Exercise:
    primary_groups = [g.lower() for g in raw.get("primaryMuscles", [])]
    secondary_groups = [g.lower() for g in raw.get("secondaryMuscles", [])]
    return Exercise(
        id=f"fedb:{raw['id']}",
        name=raw["name"],
        source="free-exercise-db",
        type=_CATEGORY_TO_TYPE.get((raw.get("category") or "strength").lower(), "strength"),
        primary_groups=primary_groups,
        secondary_groups=secondary_groups,
        primary_structures=sorted({s for g in primary_groups for s in mapping.expand(g)}),
        secondary_structures=sorted({s for g in secondary_groups for s in mapping.expand(g)}),
        equipment=[raw["equipment"]] if raw.get("equipment") else [],
        level=raw.get("level"),
        mechanic=raw.get("mechanic"),
        instructions=list(raw.get("instructions", [])),
        images=[image_base + img for img in raw.get("images", [])],
    )


def convert_all(
    raw_list: list[dict], mapping: MuscleGroupMapping, image_base: str
) -> list[Exercise]:
    out: list[Exercise] = []
    unmapped: set[str] = set()
    for raw in raw_list:
        try:
            out.append(convert_free_exercise(raw, mapping, image_base))
        except KeyError as e:  # unmapped group
            unmapped.add(str(e.args[0]))
    if unmapped:
        raise ValueError(
            "free-exercise-db uses muscle groups missing from mapping/muscle_groups.yaml: "
            + ", ".join(sorted(unmapped))
        )
    log.info("imported %d exercises", len(out))
    return out
