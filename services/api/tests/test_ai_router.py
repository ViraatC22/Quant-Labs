"""AI provider parsing, status, and free-tier failover behavior."""

from types import SimpleNamespace
from urllib.error import HTTPError

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
    assert {p["id"] for p in body["providers"]} == {
        "openai",
        "openrouter",
        "groq",
        "gemini",
        "cerebras",
        "ollama",
    }
    for provider in body["providers"]:
        assert provider["configured"] is False
        assert provider["ok"] is False
        expected = "provider disabled" if provider["id"] == "ollama" else "no API key configured"
        assert provider["error"] == expected


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


def test_openai_responses_text_parses_output_shape() -> None:
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": '{"answer_markdown": "Grounded"}'},
                ],
            }
        ]
    }
    assert ai_router._responses_text(payload) == '{"answer_markdown": "Grounded"}'


def test_ollama_text_parses_local_chat_shape() -> None:
    assert ai_router._ollama_text(
        {"message": {"role": "assistant", "content": '{"answer": "local"}'}}
    ) == '{"answer": "local"}'


def test_rate_limit_honors_retry_after_and_temporarily_skips_provider(monkeypatch) -> None:
    provider = ai_router.AiProvider(
        id="free-tier",
        label="Free tier",
        key="configured",
        model="model",
        endpoint="https://example.invalid",
        protocol="openai_chat",
    )
    error = HTTPError(
        provider.endpoint,
        429,
        "Too Many Requests",
        {"retry-after": "120"},
        None,
    )
    ai_router._provider_cooldowns.clear()
    monkeypatch.setattr(ai_router.time, "monotonic", lambda: 100.0)

    ai_router._record_rate_limit(provider, error)

    assert ai_router._provider_cooldowns[provider.id] == 220.0
    assert ai_router._provider_available(provider) is False
    monkeypatch.setattr(ai_router.time, "monotonic", lambda: 221.0)
    assert ai_router._provider_available(provider) is True


def test_research_writer_fails_over_to_next_provider_after_429(monkeypatch) -> None:
    first = ai_router.AiProvider(
        id="first-free",
        label="First free",
        key="one",
        model="model-one",
        endpoint="https://first.invalid",
        protocol="openai_chat",
    )
    second = ai_router.AiProvider(
        id="second-free",
        label="Second free",
        key="two",
        model="model-two",
        endpoint="https://second.invalid",
        protocol="openai_chat",
    )
    fake_settings = SimpleNamespace(
        research_writer_mode="auto",
        ai_provider_order=[first.id, second.id],
        ai_rate_limit_cooldown_seconds=60,
    )
    calls: list[str] = []

    def fake_complete(provider, **_kwargs):
        calls.append(provider.id)
        if provider.id == first.id:
            raise HTTPError(
                provider.endpoint,
                429,
                "Too Many Requests",
                {"retry-after": "90"},
                None,
            )
        return {"answer_markdown": "used the next provider"}

    ai_router._provider_cooldowns.clear()
    monkeypatch.setattr(ai_router, "settings", fake_settings)
    monkeypatch.setattr(ai_router, "_providers", lambda: {first.id: first, second.id: second})
    monkeypatch.setattr(ai_router, "_complete_json_with_provider", fake_complete)

    result = ai_router.complete_json_with_ai(
        system_prompt="system",
        user_prompt="user",
        response_schema={"type": "object"},
    )

    assert calls == [first.id, second.id]
    assert result is not None
    assert result.provider_id == second.id
    assert first.id in ai_router._provider_cooldowns
