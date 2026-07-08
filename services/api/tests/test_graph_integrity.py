"""Phase 2.6: shared graph nodes accumulate provenance, not last-write-wins."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def _make_doc(title: str, text: str) -> str:
    response = client.post(
        "/api/v1/vault/documents",
        json={
            "title": title,
            "document_type": "strategy",
            "content_text": text,
            "metadata": {"tags": ["orb"]},
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_shared_tag_node_records_every_contributing_source() -> None:
    _make_doc("First ORB source", "opening range breakout with volume")
    _make_doc("Second ORB source", "opening range breakout momentum continuation")

    nodes = client.get("/api/v1/graph/nodes").json()
    tag_nodes = [n for n in nodes if n["node_type"] == "tag" and n["label"] == "orb"]
    assert tag_nodes, "expected a shared 'orb' tag node"

    titles = set(tag_nodes[0]["properties"].get("source_titles", []))
    # The shared node remembers BOTH sources instead of only the latest one.
    assert {"First ORB source", "Second ORB source"} <= titles
