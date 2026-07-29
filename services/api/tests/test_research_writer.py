"""Model synthesis must remain citation-bound and fail closed."""

from datetime import UTC, datetime
from uuid import uuid4

from app.services import ai_router
from app.services.research import writer
from app.services.research.retrieval import RetrievedTrade


def _trade() -> RetrievedTrade:
    return RetrievedTrade(
        trade_id=uuid4(),
        symbol="MES",
        asset_class="future",
        side="long",
        entry_time=datetime(2026, 7, 6, 14, 45, tzinfo=UTC),
        exit_time=datetime(2026, 7, 6, 15, 10, tzinfo=UTC),
        entry_price=5600.0,
        exit_price=5590.0,
        quantity=2.0,
        contract_multiplier=5.0,
        fees=2.0,
        pnl_amount=-102.0,
        pnl_r=-1.0,
        timeframe="5m",
        session="New York",
        planned_risk_amount=100.0,
        actual_risk_amount=102.0,
        rule_adherence_score=40.0,
        emotional_state_before="chased",
        emotional_state_after="frustrated",
        journal_summary="Chased the breakout late and should have waited for the retest.",
        strategy="Opening Range Breakout",
        setup="Opening range breakout",
        score=8.0,
    )


def test_ai_writer_uses_validated_citations_and_reports_model(monkeypatch) -> None:
    trade = _trade()
    ref = f"trade:{trade.trade_id}"

    def fake_completion(**_kwargs):
        return ai_router.AiChatCompletion(
            payload={
                "answer_markdown": f"You chased the entry instead of waiting. [{ref}]",
                "used_citation_refs": [ref],
                "insufficient_evidence": False,
            },
            provider_id="openai",
            model="test-model",
        )

    monkeypatch.setattr(ai_router, "complete_json_with_ai", fake_completion)
    result = writer.compose(
        question="Why did we lose the MES trade?",
        trades=[trade],
        chunks=[],
        claims=[],
        use_ai=True,
    )

    assert result.generation_mode == "ai"
    assert result.writer_provider_id == "openai"
    assert result.writer_model == "test-model"
    assert [citation.ref for citation in result.citations] == [ref]
    assert result.trust_score == 1.0


def test_ai_writer_rejects_invented_citation_and_falls_back(monkeypatch) -> None:
    trade = _trade()
    invented = f"trade:{uuid4()}"

    def fake_completion(**_kwargs):
        return ai_router.AiChatCompletion(
            payload={
                "answer_markdown": f"Invented explanation. [{invented}]",
                "used_citation_refs": [invented],
                "insufficient_evidence": False,
            },
            provider_id="openai",
            model="test-model",
        )

    monkeypatch.setattr(ai_router, "complete_json_with_ai", fake_completion)
    result = writer.compose(
        question="Why did we lose the MES trade?",
        trades=[trade],
        chunks=[],
        claims=[],
        use_ai=True,
    )

    assert result.generation_mode == "local"
    assert "Chased the breakout" in result.answer_markdown
    assert invented not in result.answer_markdown
