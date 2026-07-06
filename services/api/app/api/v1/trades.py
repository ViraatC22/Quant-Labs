from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import Trade
from app.schemas.trades import TradeCreate, TradeRead

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


@router.post("", response_model=TradeRead, status_code=201)
def create_trade(
    payload: TradeCreate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> TradeRead:
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
        fees=payload.fees,
        pnl_amount=payload.pnl_amount,
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
