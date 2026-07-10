"""L-2: embedding-similarity entity resolution collapses synonyms to one node."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def _make_strategy(title: str, indicator: str) -> None:
    response = client.post(
        "/api/v1/vault/documents",
        json={
            "title": title,
            "document_type": "strategy",
            "content_text": f"A strategy that trades the {indicator} on the 5 minute chart.",
            "metadata": {
                "strategyInfo": {
                    "setup": "ORB",
                    "indicators": [indicator],
                }
            },
        },
    )
    assert response.status_code == 201


def test_synonym_indicators_resolve_to_one_node() -> None:
    _make_strategy("Source using the acronym", "FVG")
    _make_strategy("Source spelling it out", "fair value gap")

    nodes = client.get("/api/v1/graph/nodes").json()
    indicator_nodes = [n for n in nodes if n["node_type"] == "indicator"]
    # "FVG" and "fair value gap" are the same entity — one node, not two.
    assert len(indicator_nodes) == 1
    titles = set(indicator_nodes[0]["properties"].get("source_titles", []))
    assert {"Source using the acronym", "Source spelling it out"} <= titles


def test_distinct_indicators_stay_separate() -> None:
    _make_strategy("VWAP source", "VWAP")
    _make_strategy("RSI source", "RSI divergence")
    nodes = client.get("/api/v1/graph/nodes").json()
    labels = {n["label"] for n in nodes if n["node_type"] == "indicator"}
    assert len(labels) >= 2
