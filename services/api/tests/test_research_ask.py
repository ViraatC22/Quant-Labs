"""L-3: grounded Q&A — refuses without evidence, cites with it, trust is measured."""

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


def test_refuses_when_no_evidence() -> None:
    answer = client.post(
        "/api/v1/research/ask", json={"question": "What is my edge on opening range breakouts?"}
    ).json()
    assert answer["trust_score"] == 0.0
    assert answer["citations"] == []
    assert "don't have evidence" in answer["answer_markdown"]


def test_answers_with_resolvable_citations() -> None:
    _make_source(
        "ORB playbook",
        "The opening range breakout enters on a break of the first 15 minute range. "
        "It works well in a trending market and should be avoided in chop.",
    )
    answer = client.post(
        "/api/v1/research/ask",
        json={"question": "What does the source say about the opening range breakout?"},
    ).json()
    assert answer["trust_score"] > 0.0
    assert answer["citations"], "expected at least one citation"
    # Every citation resolves to a real chunk or claim (has a source + snippet).
    for citation in answer["citations"]:
        assert citation["kind"] in ("chunk", "claim")
        assert citation["source_title"]
        assert citation["snippet"]


def test_analytics_question_routes_to_stats_not_prose() -> None:
    answer = client.post(
        "/api/v1/research/ask", json={"question": "What is my win rate this month?"}
    ).json()
    assert answer["route"] == "analytics"
    # No trades → honest "no stats" rather than a fabricated number.
    assert "no closed trades" in answer["answer_markdown"].lower()


def test_semantic_search_beats_pure_keyword() -> None:
    _make_source(
        "Imbalance notes",
        "Price often returns to fill a fair value gap left by an impulsive move.",
    )
    # Query uses the acronym "fvg" which never appears in the source text.
    results = client.get("/api/v1/research/search", params={"q": "fvg fill"}).json()
    assert results, "synonym-aware retrieval should find the fair-value-gap chunk"


def test_conversation_history_is_recorded() -> None:
    client.post("/api/v1/research/ask", json={"question": "anything"})
    history = client.get("/api/v1/research/conversations").json()
    assert len(history) >= 1
    assert history[0]["question"] == "anything"
