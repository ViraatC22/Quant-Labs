from fastapi.testclient import TestClient

from app.main import create_app


def test_import_file_auto_extracts_text_fields() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/vault/import-file",
        files={
            "file": (
                "orb-notes.md",
                (
                    b"# ORB Strategy\nWait for VWAP, fair value gap, "
                    b"liquidity sweep, and volume confirmation."
                ),
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Orb Notes"
    assert payload["kind"] == "note"
    assert payload["source"] == "orb-notes.md"
    assert "Wait for VWAP" in payload["body"]
    assert "orb" in payload["tags"]
    assert "orb" in payload["ai_tags"]
    assert "opening-range-breakout" in payload["ai_tags"]
    assert payload["strategy_info"]["setup"] == "Opening range breakout"
    assert "Volume" in payload["strategy_info"]["indicators"]
    assert "vwap" in payload["metadata"]["technical_tags"]
    assert "fair-value-gap" in payload["metadata"]["technical_tags"]
    assert "liquidity-sweep" in payload["metadata"]["technical_tags"]
    assert "market_structure" in payload["metadata"]["technical_profile"]
    assert payload["metadata"]["enrichment_method"] == "local_semantic_rules"
    assert payload["metadata"]["ai_router"]["mode"] == "local"


def test_ai_provider_status_defaults_to_local_mode() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/vault/ai/providers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local"
    assert payload["active_provider_id"] is None
    assert [provider["id"] for provider in payload["providers"]] == [
        "openrouter",
        "groq",
        "gemini",
        "cerebras",
    ]
