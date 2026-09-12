"""Uberon: definitions, synonyms and cross-references keyed by FMA ID.

Uberon terms carry ``oboInOwl:hasDbXref "FMA:22356"`` annotations; we invert that to attach a
CC BY definition to each FMA structure. Only terms with an FMA xref are kept.
"""

from __future__ import annotations

import logging
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDFS

from pipeline.ids import is_fma, normalize_fma
from pipeline.schemas import Attributed

log = logging.getLogger(__name__)

OBO_IN_OWL = Namespace("http://www.geneontology.org/formats/oboInOwl#")
IAO_DEFINITION = URIRef("http://purl.obolibrary.org/obo/IAO_0000115")
UBERON_PREFIX = "http://purl.obolibrary.org/obo/UBERON_"


def load_uberon(path: Path) -> dict[str, dict]:
    g = Graph()
    fmt = "turtle" if path.suffix in {".ttl", ".turtle"} else "xml"
    log.info("parsing %s (%s)", path, fmt)
    g.parse(str(path), format=fmt)
    return index_by_fma(g)


def index_by_fma(g: Graph) -> dict[str, dict]:
    """Return {FMA ID: {uberon, label, definition, synonyms, wikipedia}}."""
    out: dict[str, dict] = {}
    for term, xref in g.subject_objects(OBO_IN_OWL.hasDbXref):
        xref_s = str(xref)
        if not str(term).startswith(UBERON_PREFIX) or not is_fma(xref_s):
            continue
        fma_id = normalize_fma(xref_s)
        entry = out.setdefault(
            fma_id,
            {
                "uberon": "UBERON:" + str(term)[len(UBERON_PREFIX) :],
                "label": None,
                "definition": None,
                "synonyms": [],
                "wikipedia": None,
            },
        )
        entry["label"] = str(g.value(term, RDFS.label) or "") or None
        definition = g.value(term, IAO_DEFINITION)
        entry["definition"] = str(definition) if definition else None
        entry["synonyms"] = sorted(
            {str(s) for s in g.objects(term, OBO_IN_OWL.hasExactSynonym)}
            | {str(s) for s in g.objects(term, OBO_IN_OWL.hasRelatedSynonym)}
        )
        for other in g.objects(term, OBO_IN_OWL.hasDbXref):
            if str(other).lower().startswith("wikipedia:"):
                entry["wikipedia"] = str(other).split(":", 1)[1]
    log.info("uberon: %d terms with FMA xrefs", len(out))
    return out


def definition_for(entry: dict) -> Attributed | None:
    if not entry.get("definition"):
        return None
    return Attributed(
        text=entry["definition"],
        source=f"Uberon {entry['uberon']}",
        license="CC BY 3.0",
        url="http://purl.obolibrary.org/obo/" + entry["uberon"].replace(":", "_"),
    )
