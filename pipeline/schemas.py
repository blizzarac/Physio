"""Pydantic models for the domain model (design doc §5).

These are the single source of truth for what the bundle contains and what authored content
must look like. The build pipeline validates every layer against them before emitting.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pipeline.ids import normalize_id

StructureType = Literal["muscle", "tendon", "ligament", "bone", "joint", "fascia", "region"]
ExerciseType = Literal["strength", "stretch", "activation", "isometric"]
ExerciseSource = Literal["free-exercise-db", "wger", "authored"]
PainKind = Literal["trigger_point", "strain", "tendinopathy", "referral", "compression"]
MobilizationKind = Literal["self_myofascial", "stretch", "joint_glide", "nerve_glide", "isometric"]

# Relation predicates stored in the ``relations`` table. ``crosses_joint`` is derived at build
# time; ``antagonist_of`` / ``synergist_of`` come from mapping/relations.yaml.
Predicate = Literal[
    "part_of",
    "origin",
    "insertion",
    "innervation",
    "arterial_supply",
    "crosses_joint",
    "antagonist_of",
    "synergist_of",
]


class Names(BaseModel):
    preferred: str
    latin: str | None = None
    synonyms: list[str] = Field(default_factory=list)


class Attributed(BaseModel):
    """A text value that carries its source so the UI can show attribution."""

    text: str
    source: str
    license: str | None = None
    url: str | None = None


class Relation(BaseModel):
    subject: str
    predicate: Predicate
    object: str
    source: str = "fma"

    _norm = field_validator("subject", "object")(lambda v: normalize_id(v))


class Geometry(BaseModel):
    mesh_ref: str | None = None  # relative path under static/meshes/
    centroid: tuple[float, float, float] | None = None
    bbox_min: tuple[float, float, float] | None = None
    bbox_max: tuple[float, float, float] | None = None
    triangles: int | None = None
    path: list[tuple[float, float, float]] = Field(default_factory=list)  # OpenSim, optional


class Structure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: StructureType
    names: Names
    definition: Attributed | None = None
    actions: list[Attributed] = Field(default_factory=list)
    ta2: str | None = None
    geometry: Geometry = Field(default_factory=Geometry)

    _norm = field_validator("id")(lambda v: normalize_id(v))


class Exercise(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    source: ExerciseSource
    type: ExerciseType
    primary_structures: list[str] = Field(default_factory=list)
    secondary_structures: list[str] = Field(default_factory=list)
    primary_groups: list[str] = Field(default_factory=list)  # informal names before mapping
    secondary_groups: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    level: str | None = None
    mechanic: str | None = None
    instructions: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    notes: str | None = None

    _norm = field_validator("primary_structures", "secondary_structures")(
        lambda v: [normalize_id(x) for x in v]
    )


class ContentEntry(BaseModel):
    """Common frontmatter for authored Markdown entries (design doc §9)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    sources: list[str] = Field(min_length=1)
    body: str = ""
    file: str | None = None


class PainPattern(ContentEntry):
    type: Literal["pain_pattern"] = "pain_pattern"
    structure: str
    kind: PainKind
    title: str | None = None
    description: str | None = None
    common_causes: list[str] = Field(default_factory=list)
    aggravating: list[str] = Field(default_factory=list)
    relieving: list[str] = Field(default_factory=list)
    referral_regions: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)

    _norm_s = field_validator("structure")(lambda v: normalize_id(v))
    _norm_r = field_validator("referral_regions")(lambda v: [normalize_id(x) for x in v])

    def referenced_ids(self) -> list[str]:
        return [self.structure, *self.referral_regions]


class Mobilization(ContentEntry):
    type: Literal["mobilization"] = "mobilization"
    targets: list[str] = Field(min_length=1)
    joint: str | None = None
    kind: MobilizationKind
    title: str | None = None
    steps: list[str] = Field(default_factory=list)
    duration: str | None = None
    frequency: str | None = None
    contraindications: list[str] = Field(default_factory=list)
    media: list[str] = Field(default_factory=list)

    _norm_t = field_validator("targets")(lambda v: [normalize_id(x) for x in v])
    _norm_j = field_validator("joint")(lambda v: normalize_id(v) if v else v)

    def referenced_ids(self) -> list[str]:
        return [*self.targets, *([self.joint] if self.joint else [])]


class MappingEntry(BaseModel):
    """One FMA ID inside a muscle-group mapping, with the name we expect FMA to report.

    ``expect_name`` makes a wrong-but-existing ID fail validation instead of silently mapping
    an exercise to the wrong muscle.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    expect_name: str

    _norm = field_validator("id")(lambda v: normalize_id(v))


class MuscleGroupMapping(BaseModel):
    """mapping/muscle_groups.yaml: informal exercise-db group -> FMA IDs (design doc §6)."""

    groups: dict[str, list[MappingEntry]]

    def expand(self, group: str) -> list[str]:
        key = group.strip().lower()
        if key not in self.groups:
            raise KeyError(group)
        return [e.id for e in self.groups[key]]
