"""Phase A3: a bare article is not surfaced as a tradeable strategy."""

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_plain_article_without_setup_is_not_a_recommendation() -> None:
    # A generic reference doc with no extracted setup and no matching trades
    # must not become "Favor <article title>" trade guidance.
    client.post(
        "/api/v1/vault/documents",
        json={
            "title": "Volume-weighted average price - Wikipedia",
            "document_type": "article",
            "content_text": "VWAP is the ratio of value traded to volume over a session.",
            "metadata": {"tags": ["vwap"]},
        },
    )
    recommendations = client.get("/api/v1/trades/recommendations").json()
    titles = [rec["title"] for rec in recommendations]
    assert "Volume-weighted average price - Wikipedia" not in titles
    # With no real strategy source, the fallback prompt is shown instead.
    assert any(rec["id"] == "upload-strategy-source" for rec in recommendations)


def test_source_with_real_setup_still_recommends() -> None:
    client.post(
        "/api/v1/vault/documents",
        json={
            "title": "ORB playbook",
            "document_type": "strategy",
            "content_text": (
                "Opening range breakout: go long on a break and hold above the "
                "opening range high with volume; stop below the range; target 1.5R."
            ),
            "metadata": {"tags": ["orb", "breakout"]},
        },
    )
    recommendations = client.get("/api/v1/trades/recommendations").json()
    assert any(rec["id"] != "upload-strategy-source" for rec in recommendations)
