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
        assert citation["kind"] in ("chunk", "claim", "trade")
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


def test_loss_review_uses_matching_trade_note_not_unrelated_papers() -> None:
    losing = client.post(
        "/api/v1/trades",
        json={
            "symbol": "MES",
            "asset_class": "future",
            "side": "long",
            "entry_time": "2026-07-06T14:45:00Z",
            "exit_time": "2026-07-06T15:10:00Z",
            "entry_price": "5600",
            "exit_price": "5590",
            "quantity": "2",
            "contract_multiplier": "5",
            "fees": "2",
            "emotional_state_before": "chased",
            "journal_summary": (
                "Chased the breakout late after it already ran. "
                "Should have waited for the retest."
            ),
            "metadata": {
                "strategy": "Opening Range Breakout",
                "setup": "Opening range breakout",
            },
        },
    )
    assert losing.status_code == 201
    winning = client.post(
        "/api/v1/trades",
        json={
            "symbol": "MES",
            "asset_class": "future",
            "side": "long",
            "entry_time": "2026-07-09T14:45:00Z",
            "exit_time": "2026-07-09T15:10:00Z",
            "entry_price": "5600",
            "exit_price": "5606.5",
            "quantity": "2",
            "contract_multiplier": "5",
            "fees": "1.25",
            "journal_summary": "Waited for confirmation and followed the plan.",
            "metadata": {"strategy": "Opening Range Breakout"},
        },
    )
    assert winning.status_code == 201
    _make_source(
        "Opening range breakout playbook",
        "Mark the first 15-minute high and low. Wait for confirmation before entry.",
    )
    _make_source(
        "Signature-Based Optimal Execution for Statistical Arbitrage",
        "A path-dependent signature model controls statistical-arbitrage execution speed.",
    )

    answer = client.post(
        "/api/v1/research/ask",
        json={"question": "Why did we lose the MES trade?"},
    ).json()

    assert answer["route"] == "trade_review"
    assert answer["generation_mode"] == "local"
    assert "chased" in answer["answer_markdown"].lower()
    assert "retest" in answer["answer_markdown"].lower()
    assert "signature-based" not in answer["answer_markdown"].lower()
    assert answer["citations"][0]["kind"] == "trade"
    assert answer["retrieved"]["trades"][0]["trade_id"] == losing.json()["id"]
    assert all(
        "signature-based" not in chunk["source_title"].lower()
        for chunk in answer["retrieved"]["chunks"]
    )
