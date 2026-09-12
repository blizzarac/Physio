"""Parse the FMA OWL export with rdflib and extract the musculoskeletal subset.

The FMA OWL (purl.org/sig/ont/fma) expresses relations as ``rdfs:subClassOf`` restrictions::

    fma:fma22356 rdfs:subClassOf [ a owl:Restriction ;
                                   owl:onProperty fma:origin ;
                                   owl:someValuesFrom fma:fma24474 ] .

and names/synonyms as annotation properties (``fma:preferred_name``, ``fma:synonym``,
``fma:TA_ID``). This module walks the subclass tree from the configured MSK roots, assigns a
``StructureType`` from the root, and collects the relations listed in ``RELATION_PROPERTIES``.

The full FMA is large (~300 MB RDF/XML); parsing takes a while. Results are cached as JSON by
the CLI so later steps are fast.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import RDF, RDFS, Graph, Namespace, URIRef
from rdflib.namespace import OWL

from pipeline.config import MskRoots
from pipeline.ids import fma_to_iri, iri_to_fma
from pipeline.schemas import Names, Relation, Structure, StructureType

log = logging.getLogger(__name__)

FMA = Namespace("http://purl.org/sig/ont/fma/")

# FMA property IRI -> our predicate. Both regional and constitutional part-of collapse to part_of.
RELATION_PROPERTIES: dict[URIRef, str] = {
    FMA.origin: "origin",
    FMA.insertion: "insertion",
    FMA.nerve_supply: "innervation",
    FMA.arterial_supply: "arterial_supply",
    FMA.regional_part_of: "part_of",
    FMA.constitutional_part_of: "part_of",
    FMA.part_of: "part_of",
}


@dataclass
class FmaSubset:
    structures: dict[str, Structure] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    # Names of *all* FMA classes touched by a relation, so bones/nerves referenced from a
    # muscle can be labelled even when they are outside the subset roots.
    labels: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "structures": {k: v.model_dump(mode="json") for k, v in self.structures.items()},
            "relations": [r.model_dump(mode="json") for r in self.relations],
            "labels": self.labels,
        }

    @classmethod
    def from_json(cls, data: dict) -> FmaSubset:
        return cls(
            structures={k: Structure.model_validate(v) for k, v in data["structures"].items()},
            relations=[Relation.model_validate(r) for r in data["relations"]],
            labels=dict(data.get("labels", {})),
        )


def load_graph(path: Path) -> Graph:
    g = Graph()
    fmt = "turtle" if path.suffix in {".ttl", ".turtle"} else "xml"
    log.info("parsing %s (%s)", path, fmt)
    g.parse(str(path), format=fmt)
    log.info("parsed %d triples", len(g))
    return g


def _label(g: Graph, node: URIRef) -> str | None:
    for prop in (FMA.preferred_name, RDFS.label):
        for value in g.objects(node, prop):
            return str(value)
    return None


def _synonyms(g: Graph, node: URIRef) -> list[str]:
    return sorted({str(v) for v in g.objects(node, FMA.synonym)})


def _ta_id(g: Graph, node: URIRef) -> str | None:
    for v in g.objects(node, FMA.TA_ID):
        return str(v)
    return None


def _subclasses(g: Graph, node: URIRef):
    yield from g.subjects(RDFS.subClassOf, node)


def _restrictions(g: Graph, node: URIRef):
    """Yield (property, filler) for every someValuesFrom restriction on ``node``."""
    for parent in g.objects(node, RDFS.subClassOf):
        if (parent, RDF.type, OWL.Restriction) not in g:
            continue
        prop = g.value(parent, OWL.onProperty)
        filler = g.value(parent, OWL.someValuesFrom)
        if prop is None or filler is None:
            continue
        yield prop, filler


def collect_subtree(g: Graph, root: URIRef) -> set[URIRef]:
    seen: set[URIRef] = set()
    queue = deque([root])
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(_subclasses(g, node))
    return seen


def extract_msk_subset(g: Graph, roots: MskRoots) -> FmaSubset:
    subset = FmaSubset()
    type_of: dict[URIRef, StructureType] = {}

    for type_name, fma_id, expected in roots.items():
        root = URIRef(fma_to_iri(fma_id))
        label = _label(g, root)
        if label is None:
            log.warning("MSK root %s (%s) not found in FMA graph; skipping", fma_id, expected)
            continue
        if label.lower() != expected.lower():
            raise ValueError(
                f"MSK root {fma_id} is labelled {label!r}, expected {expected!r}; "
                "check pipeline/config.py MskRoots"
            )
        members = collect_subtree(g, root)
        log.info("root %s (%s): %d classes", fma_id, label, len(members))
        for node in members:
            # A class may be reachable from several roots (e.g. a joint that is also a region);
            # the first root in MskRoots order wins.
            type_of.setdefault(node, type_name)  # type: ignore[arg-type]

    for node, stype in type_of.items():
        fma_id = iri_to_fma(str(node))
        if fma_id is None:
            continue
        name = _label(g, node)
        if not name:
            continue
        subset.structures[fma_id] = Structure(
            id=fma_id,
            type=stype,
            names=Names(preferred=name, synonyms=_synonyms(g, node)),
            ta2=_ta_id(g, node),
        )
        subset.labels[fma_id] = name
        for prop, filler in _restrictions(g, node):
            predicate = RELATION_PROPERTIES.get(prop)
            target = iri_to_fma(str(filler)) if isinstance(filler, URIRef) else None
            if predicate is None or target is None:
                continue
            subset.relations.append(
                Relation(subject=fma_id, predicate=predicate, object=target)  # type: ignore[arg-type]
            )
            if target not in subset.labels:
                target_label = _label(g, filler)
                if target_label:
                    subset.labels[target] = target_label

    _add_region_ancestors(g, subset)

    # Deduplicate relations while preserving order.
    seen: set[tuple[str, str, str]] = set()
    unique: list[Relation] = []
    for r in subset.relations:
        key = (r.subject, r.predicate, r.object)
        if key not in seen:
            seen.add(key)
            unique.append(r)
    subset.relations = unique
    log.info("MSK subset: %d structures, %d relations", len(subset.structures), len(unique))
    return subset


REGION_PROPERTIES = (FMA.regional_part_of, FMA.part_of)
MAX_REGION_DEPTH = 12


def _add_region_ancestors(g: Graph, subset: FmaSubset) -> None:
    """Follow ``regional_part_of`` upward from every subset member and add the regions found
    (thigh, lower limb, ...) as ``region`` structures so the viewer can navigate a hierarchy.
    Chains are capped at MAX_REGION_DEPTH; cycles are ignored."""
    queue: deque[tuple[URIRef, int]] = deque()
    for fma_id in list(subset.structures):
        queue.append((URIRef(fma_to_iri(fma_id)), 0))
    seen: set[URIRef] = set()
    added = 0
    while queue:
        node, depth = queue.popleft()
        if node in seen or depth > MAX_REGION_DEPTH:
            continue
        seen.add(node)
        child_id = iri_to_fma(str(node))
        if child_id is None:
            continue
        for prop, filler in _restrictions(g, node):
            if prop not in REGION_PROPERTIES or not isinstance(filler, URIRef):
                continue
            parent_id = iri_to_fma(str(filler))
            if parent_id is None:
                continue
            if parent_id not in subset.structures:
                name = _label(g, filler)
                if not name:
                    continue
                subset.structures[parent_id] = Structure(
                    id=parent_id,
                    type="region",
                    names=Names(preferred=name, synonyms=_synonyms(g, filler)),
                    ta2=_ta_id(g, filler),
                )
                subset.labels[parent_id] = name
                added += 1
            subset.relations.append(
                Relation(subject=child_id, predicate="part_of", object=parent_id)
            )
            queue.append((filler, depth + 1))
    log.info("region hierarchy: added %d region structures", added)


def derive_crosses_joint(
    subset: FmaSubset, joints: dict[frozenset[str], str]
) -> tuple[list[Relation], list[tuple[str, str, str]]]:
    """A muscle whose origin and insertion sit on different bones crosses a joint (§5).

    ``joints`` maps a bone pair (from ``mapping/joints.yaml``) to the joint's FMA ID. Returns
    the derived relations plus the (muscle, bone, bone) pairs that no joint entry covers, so
    the mapping table can be extended.
    """
    by_subject: dict[str, dict[str, set[str]]] = {}
    for r in subset.relations:
        if r.predicate in ("origin", "insertion"):
            by_subject.setdefault(r.subject, {}).setdefault(r.predicate, set()).add(r.object)
    derived: list[Relation] = []
    unresolved: list[tuple[str, str, str]] = []
    for subject, preds in by_subject.items():
        for o in sorted(preds.get("origin", set())):
            for i in sorted(preds.get("insertion", set())):
                if o == i:
                    continue
                joint = joints.get(frozenset((o, i)))
                if joint is None:
                    unresolved.append((subject, o, i))
                    continue
                derived.append(
                    Relation(
                        subject=subject, predicate="crosses_joint", object=joint, source="derived"
                    )
                )
    return derived, unresolved
