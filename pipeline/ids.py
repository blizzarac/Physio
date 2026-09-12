"""Canonical identifier handling (design doc §4).

Every entity resolves to an FMA ID written as ``FMA:<digits>``. Structures with no FMA
entry get a local ID in the ``ax:`` namespace, documented in ``mapping/local_ids.yaml``.
"""

from __future__ import annotations

import re

FMA_IRI_PREFIX = "http://purl.org/sig/ont/fma/fma"
_FMA_RE = re.compile(r"^(?:FMA[:_ ]?|fma)?(\d+)$")
_AX_RE = re.compile(r"^ax:[a-z0-9][a-z0-9-]*$")


def normalize_fma(value: str) -> str:
    """Accept ``FMA:22356``, ``FMA22356``, ``fma22356``, ``22356`` and return ``FMA:22356``."""
    value = value.strip()
    if value.startswith(FMA_IRI_PREFIX):
        value = value[len(FMA_IRI_PREFIX) :]
    m = _FMA_RE.match(value)
    if not m:
        raise ValueError(f"not an FMA identifier: {value!r}")
    return f"FMA:{int(m.group(1))}"


def normalize_id(value: str) -> str:
    """Normalize either an FMA ID or a local ``ax:`` ID."""
    value = value.strip()
    if _AX_RE.match(value):
        return value
    return normalize_fma(value)


def is_fma(value: str) -> bool:
    try:
        normalize_fma(value)
        return True
    except ValueError:
        return False


def fma_to_iri(fma_id: str) -> str:
    return FMA_IRI_PREFIX + normalize_fma(fma_id).split(":")[1]


def iri_to_fma(iri: str) -> str | None:
    if iri.startswith(FMA_IRI_PREFIX):
        try:
            return normalize_fma(iri)
        except ValueError:
            return None
    return None
