"""Optional Wikidata layer: short descriptions, muscle actions, images, keyed by FMA ID.

Runs one SPARQL query for all items with an FMA ID (P1402) and caches the result as JSON.
Wikidata text is CC0; Wikipedia summaries (if fetched later) are CC BY-SA and must stay in a
separately attributed field (design doc §3 licensing note).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from pipeline.ids import normalize_fma
from pipeline.schemas import Attributed

log = logging.getLogger(__name__)

QUERY = """
SELECT ?item ?itemLabel ?itemDescription ?fma ?action ?actionLabel ?image ?enwiki WHERE {
  ?item wdt:P1402 ?fma .
  OPTIONAL { ?item wdt:P18 ?image . }
  OPTIONAL { ?item wdt:P3094 ?action . }   # muscle action
  OPTIONAL { ?enwiki schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de,el". }
}
"""


def fetch_wikidata(endpoint: str, out_file: Path, timeout: float = 300.0) -> dict[str, dict]:
    headers = {"Accept": "application/sparql-results+json", "User-Agent": "anatomy-explorer/0.1"}
    resp = httpx.get(endpoint, params={"query": QUERY}, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = index_results(resp.json())
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return data


def index_results(payload: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in payload.get("results", {}).get("bindings", []):
        try:
            fma_id = normalize_fma(row["fma"]["value"])
        except (KeyError, ValueError):
            continue
        entry = out.setdefault(
            fma_id,
            {
                "qid": row["item"]["value"].rsplit("/", 1)[-1],
                "label": None,
                "description": None,
                "actions": [],
                "images": [],
                "enwiki": None,
            },
        )
        entry["label"] = row.get("itemLabel", {}).get("value") or entry["label"]
        entry["description"] = row.get("itemDescription", {}).get("value") or entry["description"]
        if "actionLabel" in row and row["actionLabel"]["value"] not in entry["actions"]:
            entry["actions"].append(row["actionLabel"]["value"])
        if "image" in row and row["image"]["value"] not in entry["images"]:
            entry["images"].append(row["image"]["value"])
        if "enwiki" in row:
            entry["enwiki"] = row["enwiki"]["value"]
    return out


def load_wikidata(path: Path) -> dict[str, dict]:
    return json.loads(path.read_text())


def actions_for(entry: dict) -> list[Attributed]:
    return [
        Attributed(
            text=a,
            source=f"Wikidata {entry['qid']}",
            license="CC0",
            url=f"https://www.wikidata.org/wiki/{entry['qid']}",
        )
        for a in entry.get("actions", [])
    ]
