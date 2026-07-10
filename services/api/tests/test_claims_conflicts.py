"""L-4: claim extraction and conflict detection between disagreeing sources."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def _make_source(title: str, text: str) -> None:
    response = client.post(
        "/api/v1/vault/documents",
        json={
            "title": title,
            "document_type": "strategy",
            "content_text": text,
            "metadata": {"strategyInfo": {"setup": "ORB", "market": "futures"}},
        },
    )
    assert response.status_code == 201


def test_opposing_sources_produce_one_conflict() -> None:
    _make_source("Bull case", "The ORB works well in chop and ranging conditions.")
    _make_source("Bear case", "The ORB does not work in chop; avoid it when ranging.")

    conflicts = client.get("/api/v1/research/conflicts").json()
    assert len(conflicts) == 1
    pair = {conflicts[0]["claim_a"]["polarity"], conflicts[0]["claim_b"]["polarity"]}
    assert pair == {"supports", "refutes"}


def test_claims_are_created_and_listable() -> None:
    _make_source("Single source", "The ORB works well in a trend.")
    claims = client.get("/api/v1/research/claims").json()
    assert any(c["predicate"] == "works_in" for c in claims)


def test_conflict_can_be_dismissed() -> None:
    _make_source("Bull case", "The ORB works well in chop.")
    _make_source("Bear case", "The ORB never works in chop.")
    conflicts = client.get("/api/v1/research/conflicts").json()
    assert conflicts
    conflict_id = conflicts[0]["id"]
    resolved = client.patch(
        f"/api/v1/research/conflicts/{conflict_id}",
        json={"status": "dismissed", "resolution_note": "same author"},
    )
    assert resolved.status_code == 200
    assert client.get("/api/v1/research/conflicts").json() == []


def test_claim_timeline_returns_evidence_points() -> None:
    _make_source("Source one", "The ORB works well in a trend.")
    _make_source("Source two", "The ORB works well in a trend.")
    claims = client.get("/api/v1/research/claims").json()
    trend_claim = next(c for c in claims if c["object_literal"] == "trend")
    timeline = client.get(f"/api/v1/research/claims/{trend_claim['id']}/timeline").json()
    # Two sources reinforcing the same claim → two evidence points.
    assert len(timeline) == 2
