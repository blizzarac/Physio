from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture
def client(built_bundle, content_copy: Path):
    app = create_app(bundle_dir=built_bundle.bundle_dir, content_dir=content_copy, watch=False)
    with TestClient(app) as c:
        yield c


def test_structure_endpoint(client: TestClient):
    r = client.get("/structures/FMA22356")  # accepts unnormalized IDs
    assert r.status_code == 200
    s = r.json()
    assert s["id"] == "FMA:22356" and s["names"]["preferred"] == "Biceps femoris"
    assert s["geometry"]["mesh_url"] == "/static/meshes/FMA22356.glb"
    assert s["relations"]["origin"][0] == {
        "id": "FMA:16580",
        "name": "Hip bone",
        "source": "fma",
        "resolvable": True,
    }
    # innervation targets (nerves) sit outside the MSK subset: labelled, but no page to link to
    assert s["relations"]["innervation"][0]["name"] == "Tibial nerve"
    assert s["relations"]["innervation"][0]["resolvable"] is False
    assert s["counts"] == {"exercises": 1, "pain_patterns": 0, "mobilizations": 0}
    assert client.get("/structures/FMA:1").status_code == 404
    assert client.get("/structures/nonsense").status_code == 400
    # mesh is served
    assert client.get(s["geometry"]["mesh_url"]).status_code == 200


def test_related_and_incoming(client: TestClient):
    r = client.get("/structures/FMA:22356/related").json()
    assert [a["id"] for a in r["antagonists"]] == ["FMA:22314"]
    assert [a["id"] for a in r["synergists"]] == ["FMA:22357"]
    bone = client.get("/structures/FMA:16580").json()
    assert {x["id"] for x in bone["incoming"]["origin"]} >= {"FMA:22356", "FMA:22314"}


def test_search(client: TestClient):
    hits = client.get("/search", params={"q": "glut"}).json()
    assert {h["id"] for h in hits} == {"FMA:22314", "FMA:22315", "FMA:22317"}
    hits = client.get("/search", params={"q": "musculus biceps"}).json()
    assert hits[0]["id"] == "FMA:22356" and hits[0]["matched_kind"] == "synonym"
    assert client.get("/search", params={"q": ""}).status_code == 422


def test_exercises(client: TestClient):
    r = client.get("/exercises", params={"structure": "FMA:22314"}).json()
    assert r["total"] == 1 and r["items"][0]["role"] == "secondary"
    r = client.get("/exercises", params={"structure": "FMA:22314", "role": "primary"}).json()
    assert r["total"] == 0
    r = client.get("/exercises", params={"type": "stretch"}).json()
    assert [e["id"] for e in r["items"]] == ["fedb:Upper_Trapezius_Stretch"]
    r = client.get("/exercises", params={"equipment": "barbell"}).json()
    assert r["total"] == 1
    ex = client.get("/exercises/fedb:Romanian_Deadlift").json()
    assert {(s["id"], s["role"]) for s in ex["structures"]} >= {("FMA:22356", "primary")}
    assert client.get("/exercises/filters").json()["equipment"] == ["barbell"]


def test_pain_and_mobilization_with_reload(client: TestClient, content_copy: Path):
    r = client.get("/pain/FMA:9626").json()
    assert "anatomical education" in r["disclaimer"]
    assert len(r["items"]) == 1
    item = r["items"][0]
    assert item["structure"] == {"id": "FMA:9626", "name": "Trapezius"}
    assert item["referral_regions"][0]["name"] == "Levator scapulae"
    assert item["sources"][0]["id"] == "travell-simons-vol1"
    assert "Trigger Point Manual" in item["sources"][0]["title"]
    # a referral region is also found via the region's own ID
    assert len(client.get("/pain/FMA:32519").json()["items"]) == 1
    # mobilization found via its target and via its joint
    assert len(client.get("/mobilizations/FMA:22315").json()["items"]) == 1
    assert len(client.get("/mobilizations/FMA:24964").json()["items"]) == 1

    # hot reload: add a new file with a bad reference, reload, see it reported but not served
    (content_copy / "pain" / "new.md").write_text(
        "---\ntype: pain_pattern\nid: pp-new\nstructure: FMA:22317\nkind: strain\n"
        "referral_regions: [FMA:424242]\nsources: [x]\n---\nbody\n"
    )
    status = client.post("/content/reload").json()
    assert status["pain_patterns"] == 2
    assert any("FMA:424242" in e for e in status["reference_errors"])
    assert len(client.get("/pain/FMA:22317").json()["items"]) == 1
