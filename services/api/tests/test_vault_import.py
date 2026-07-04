from fastapi.testclient import TestClient

from app.main import create_app


def test_import_file_auto_extracts_text_fields() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/vault/import-file",
        files={
            "file": (
                "orb-notes.md",
                b"# ORB Strategy\nWait for volume confirmation.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Orb Notes"
    assert payload["kind"] == "note"
    assert payload["source"] == "orb-notes.md"
    assert "Wait for volume confirmation" in payload["body"]
    assert "orb" in payload["tags"]
    assert "orb" in payload["ai_tags"]
    assert "opening-range-breakout" in payload["ai_tags"]
    assert payload["strategy_info"]["setup"] == "Opening range breakout"
    assert "Volume" in payload["strategy_info"]["indicators"]
