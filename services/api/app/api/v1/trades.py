from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import JournalEntry, SourceDocument, Trade
from app.schemas.trades import (
    MarketQuoteRead,
    StrategyEvaluationRead,
    StrategyEvaluationRequest,
    TradeCreate,
    TradeRead,
    TradeRecommendationRead,
    TradeUpdate,
)
from app.services.market_data import MarketQuote, fetch_market_quote
from app.services.strategy_evaluation import (
    StrategyEvaluation,
    build_optimal_strategy,
    evaluate_strategy_idea,
    evaluation_journal_body,
)
from app.services.trade_recommendations import build_trade_recommendations

router = APIRouter()


def _trade_read(trade: Trade) -> TradeRead:
    return TradeRead(
        id=trade.id,
        symbol=trade.symbol,
        asset_class=trade.asset_class,
        side=trade.side,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        quantity=trade.quantity,
        contract_multiplier=trade.contract_multiplier,
        fees=trade.fees,
        pnl_amount=trade.pnl_amount,
        pnl_r=trade.pnl_r,
        strategy_version_id=trade.strategy_version_id,
        setup_id=trade.setup_id,
        timeframe=trade.timeframe,
        session=trade.session,
        market_regime_id=trade.market_regime_id,
        planned_risk_amount=trade.planned_risk_amount,
        actual_risk_amount=trade.actual_risk_amount,
        rule_adherence_score=trade.rule_adherence_score,
        emotional_state_before=trade.emotional_state_before,
        emotional_state_after=trade.emotional_state_after,
        journal_summary=trade.journal_summary,
        metadata=trade.trade_metadata,
        created_at=trade.created_at,
        updated_at=trade.updated_at,
    )


def _quote_read(quote: MarketQuote) -> MarketQuoteRead:
    return MarketQuoteRead(
        symbol=quote.symbol,
        provider_symbol=quote.provider_symbol,
        provider=quote.provider,
        last_price=quote.last_price,
        previous_close=quote.previous_close,
        currency=quote.currency,
        market_time=quote.market_time,
        delayed=quote.delayed,
    )


def _evaluation_read(
    evaluation: StrategyEvaluation,
    *,
    journal_entry_id: UUID | None = None,
) -> StrategyEvaluationRead:
    return StrategyEvaluationRead(
        title=evaluation.title,
        decision=evaluation.decision,
        score=evaluation.score,
        confidence=evaluation.confidence,
        rationale=evaluation.rationale,
        technical_tags=evaluation.technical_tags,
        technical_profile=evaluation.technical_profile,
        included=evaluation.included,
        excluded=evaluation.excluded,
        draft=evaluation.draft,
        journal_entry_id=journal_entry_id,
    )


def _compute_pnl(
    *,
    side: str,
    entry_price: Decimal,
    exit_price: Decimal | None,
    quantity: Decimal,
    contract_multiplier: Decimal,
    fees: Decimal,
) -> Decimal | None:
    if exit_price is None:
        return None
    direction = Decimal("1") if side == "long" else Decimal("-1")
    return (exit_price - entry_price) * quantity * contract_multiplier * direction - fees


def _user_sources_and_trades(
    db: Session,
    user_id: UUID,
) -> tuple[list[SourceDocument], list[Trade]]:
    sources = list(
        db.scalars(
            select(SourceDocument)
            .where(SourceDocument.user_id == user_id)
            .order_by(SourceDocument.created_at.desc())
        ).all()
    )
    trades = list(
        db.scalars(
            select(Trade).where(Trade.user_id == user_id).order_by(Trade.entry_time.desc())
        ).all()
    )
    return sources, trades


def _quote_or_none(symbol: str | None) -> MarketQuote | None:
    if not symbol:
        return None
    try:
        return fetch_market_quote(symbol)
    except (OSError, TimeoutError, ValueError):
        return None


@router.post("", response_model=TradeRead, status_code=201)
def create_trade(
    payload: TradeCreate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> TradeRead:
    pnl_amount = payload.pnl_amount
    if pnl_amount is None:
        pnl_amount = _compute_pnl(
            side=payload.side,
            entry_price=payload.entry_price,
            exit_price=payload.exit_price,
            quantity=payload.quantity,
            contract_multiplier=payload.contract_multiplier,
            fees=payload.fees,
        )

    # Honor a client-supplied UUID so an offline-created trade replays
    # idempotently once the API is reachable again (see the sync queue).
    if payload.id is not None and db.get(Trade, payload.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A trade with this id already exists.",
        )

    trade = Trade(
        user_id=user_id,
        symbol=payload.symbol.upper(),
        asset_class=payload.asset_class,
        side=payload.side,
        entry_time=payload.entry_time,
        exit_time=payload.exit_time,
        entry_price=payload.entry_price,
        exit_price=payload.exit_price,
        quantity=payload.quantity,
        contract_multiplier=payload.contract_multiplier,
        fees=payload.fees,
        pnl_amount=pnl_amount,
        pnl_r=payload.pnl_r,
        strategy_version_id=payload.strategy_version_id,
        setup_id=payload.setup_id,
        timeframe=payload.timeframe,
        session=payload.session,
        market_regime_id=payload.market_regime_id,
        planned_risk_amount=payload.planned_risk_amount,
        actual_risk_amount=payload.actual_risk_amount,
        rule_adherence_score=payload.rule_adherence_score,
        emotional_state_before=payload.emotional_state_before,
        emotional_state_after=payload.emotional_state_after,
        journal_summary=payload.journal_summary,
        trade_metadata=payload.metadata,
    )
    if payload.id is not None:
        trade.id = payload.id
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return _trade_read(trade)


@router.get("", response_model=list[TradeRead])
def list_trades(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[TradeRead]:
    trades = db.scalars(
        select(Trade).where(Trade.user_id == user_id).order_by(Trade.entry_time.desc())
    ).all()
    return [_trade_read(trade) for trade in trades]


@router.get("/quotes/{symbol}", response_model=MarketQuoteRead)
def get_quote(symbol: str) -> MarketQuoteRead:
    try:
        quote = fetch_market_quote(symbol)
    except (OSError, TimeoutError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not fetch market quote for {symbol}.",
        ) from exc
    return _quote_read(quote)


@router.get("/recommendations", response_model=list[TradeRecommendationRead])
def list_trade_recommendations(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[TradeRecommendationRead]:
    sources, trades = _user_sources_and_trades(db, user_id)
    return build_trade_recommendations(sources=sources, trades=trades)


@router.get("/strategy/optimal", response_model=StrategyEvaluationRead)
def optimal_strategy(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> StrategyEvaluationRead:
    sources, trades = _user_sources_and_trades(db, user_id)
    evaluation = build_optimal_strategy(sources=sources, trades=trades)
    quote = _quote_or_none(evaluation.draft.get("symbol"))
    if quote:
        evaluation = build_optimal_strategy(sources=sources, trades=trades, quote=quote)
    return _evaluation_read(evaluation)


@router.post("/strategy/evaluate", response_model=StrategyEvaluationRead)
def evaluate_strategy(
    payload: StrategyEvaluationRequest,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> StrategyEvaluationRead:
    sources, trades = _user_sources_and_trades(db, user_id)
    quote = _quote_or_none(payload.symbol)
    evaluation = evaluate_strategy_idea(
        idea=payload.idea,
        sources=sources,
        trades=trades,
        symbol=payload.symbol,
        quote=quote,
    )
    if quote is None:
        quote = _quote_or_none(evaluation.draft.get("symbol"))
        if quote:
            evaluation = evaluate_strategy_idea(
                idea=payload.idea,
                sources=sources,
                trades=trades,
                symbol=evaluation.draft.get("symbol"),
                quote=quote,
            )

    journal_entry_id = None
    if payload.save_journal:
        entry = JournalEntry(
            user_id=user_id,
            entry_date=date.today(),
            title=f"AI strategy evaluation: {evaluation.title[:180]}",
            body=evaluation_journal_body(evaluation),
            emotional_state="analytical",
            tags=["ai-evaluation", evaluation.decision, *evaluation.technical_tags[:8]],
            journal_metadata={"evaluation": _evaluation_read(evaluation).model_dump(mode="json")},
        )
        db.add(entry)
        db.flush()
        journal_entry_id = entry.id
        db.commit()

    return _evaluation_read(evaluation, journal_entry_id=journal_entry_id)


@router.patch("/{trade_id}", response_model=TradeRead)
def update_trade(
    trade_id: UUID,
    payload: TradeUpdate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> TradeRead:
    trade = db.get(Trade, trade_id)
    if trade is None or trade.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found.")

    fields_set = payload.model_fields_set

    if payload.exit_price is not None:
        trade.exit_price = payload.exit_price
        trade.exit_time = payload.exit_time or datetime.now(UTC)
    if payload.exit_time is not None:
        trade.exit_time = payload.exit_time
    if payload.contract_multiplier is not None:
        trade.contract_multiplier = payload.contract_multiplier
    if payload.fees is not None:
        trade.fees = payload.fees
    if payload.emotional_state_after is not None:
        trade.emotional_state_after = payload.emotional_state_after
    if payload.journal_summary is not None:
        trade.journal_summary = payload.journal_summary
    if payload.metadata is not None:
        trade.trade_metadata = {**(trade.trade_metadata or {}), **payload.metadata}

    # Only touch P&L when the caller explicitly sends the field. Omitting it must
    # not wipe a manually recorded (e.g. broker-adjusted) value.
    if "pnl_amount" in fields_set:
        trade.pnl_amount = payload.pnl_amount
    if trade.pnl_amount is None:
        trade.pnl_amount = _compute_pnl(
            side=trade.side,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            contract_multiplier=trade.contract_multiplier,
            fees=trade.fees,
        )
    if "pnl_r" in fields_set:
        trade.pnl_r = payload.pnl_r
    db.commit()
    db.refresh(trade)
    return _trade_read(trade)


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trade(
    trade_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:
    trade = db.get(Trade, trade_id)
    if trade is None or trade.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found.")
    db.delete(trade)
    db.commit()
