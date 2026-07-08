"""Phase 2.5: AI provider self-test and Gemini request shape."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.services import ai_router

client = TestClient(create_app())


def test_self_test_reports_each_provider_without_keys() -> None:
    # Tests run with AI_ENRICHMENT_MODE=local and no provider keys, so the
    # self-test must report every provider as unconfigured rather than error.
    response = client.get("/api/v1/vault/ai/providers/self-test")
    assert response.status_code == 200
    body = response.json()
    assert {p["id"] for p in body["providers"]} == {"openrouter", "groq", "gemini", "cerebras"}
    for provider in body["providers"]:
        assert provider["configured"] is False
        assert provider["ok"] is False
        assert provider["error"] == "no API key configured"


def test_gemini_text_parses_generatecontent_shape() -> None:
    payload = {
        "candidates": [
            {"content": {"parts": [{"text": '{"title": "X"}'}]}},
        ]
    }
    assert ai_router._gemini_text(payload) == '{"title": "X"}'


def test_gemini_text_raises_on_empty() -> None:
    import pytest

    with pytest.raises(ValueError):
        ai_router._gemini_text({"candidates": []})
