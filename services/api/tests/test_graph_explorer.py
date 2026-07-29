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
    assert all("open_conflict_count" in node for node in neighborhood["nodes"])
    assert all("evidence_count" in edge for edge in neighborhood["edges"])
    assert any(edge["evidence"] for edge in neighborhood["edges"])
    evidence = next(edge["evidence"] for edge in neighborhood["edges"] if edge["evidence"])
    assert evidence[0]["source_title"] == "ORB strategy"
    assert evidence[0]["source_document_id"]


def test_neighborhood_404_for_unknown_node() -> None:
    missing = "00000000-0000-0000-0000-0000000000ff"
    assert client.get(f"/api/v1/graph/neighborhood/{missing}").status_code == 404


def test_graph_lists_support_pagination_and_scoping() -> None:
    _seed()
    nodes = client.get("/api/v1/graph/nodes").json()
    assert len(client.get("/api/v1/graph/nodes", params={"limit": 2}).json()) == 2
    strategy = next(node for node in nodes if node["node_type"] == "strategy")
    scoped = client.get(
        "/api/v1/graph/edges", params={"node_id": strategy["id"], "limit": 100}
    ).json()
    assert scoped
    assert all(
        strategy["id"] in {edge["from_node_id"], edge["to_node_id"]}
        for edge in scoped
    )


def test_conflicted_subject_is_badged_in_neighborhood() -> None:
    client.post(
        "/api/v1/vault/documents",
        json={
            "title": "ORB bull",
            "document_type": "strategy",
            "content_text": "The ORB works well in chop.",
            "metadata": {"strategyInfo": {"name": "ORB", "setup": "ORB"}},
        },
    )
    client.post(
        "/api/v1/vault/documents",
        json={
            "title": "ORB bear",
            "document_type": "strategy",
            "content_text": "The ORB never works in chop.",
            "metadata": {"strategyInfo": {"name": "ORB", "setup": "ORB"}},
        },
    )
    strategy = next(
        node
        for node in client.get("/api/v1/graph/nodes").json()
        if node["node_type"] == "strategy" and node["label"] == "ORB"
    )
    neighborhood = client.get(
        f"/api/v1/graph/neighborhood/{strategy['id']}"
    ).json()
    subject = next(node for node in neighborhood["nodes"] if node["id"] == strategy["id"])
    assert subject["open_conflict_count"] == 1
