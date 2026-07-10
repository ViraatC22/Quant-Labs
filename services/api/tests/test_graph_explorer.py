"""L-5: neighborhood expansion and entity search endpoints."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def _seed() -> None:
    client.post(
        "/api/v1/vault/documents",
        json={
            "title": "ORB strategy",
            "document_type": "strategy",
            "content_text": "Opening range breakout on 5 minute chart in futures.",
            "metadata": {
                "strategyInfo": {
                    "setup": "ORB",
                    "indicators": ["VWAP"],
                    "market": "futures",
                    "timeframe": "5m",
                }
            },
        },
    )


def test_entity_search_finds_nodes() -> None:
    _seed()
    results = client.get("/api/v1/graph/search", params={"q": "ORB"}).json()
    assert any("ORB" in n["label"] or n["node_type"] == "strategy" for n in results)


def test_neighborhood_expands_from_strategy() -> None:
    _seed()
    nodes = client.get("/api/v1/graph/nodes").json()
    strategy = next(n for n in nodes if n["node_type"] == "strategy")
    neighborhood = client.get(
        f"/api/v1/graph/neighborhood/{strategy['id']}", params={"depth": 1}
    ).json()
    assert neighborhood["root_id"] == strategy["id"]
    # The strategy connects out to setup/indicator/market/timeframe nodes.
    assert len(neighborhood["nodes"]) > 1
    assert neighborhood["edges"]


def test_neighborhood_404_for_unknown_node() -> None:
    missing = "00000000-0000-0000-0000-0000000000ff"
    assert client.get(f"/api/v1/graph/neighborhood/{missing}").status_code == 404
