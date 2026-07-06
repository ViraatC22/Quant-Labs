from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class TradeCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    asset_class: str = Field(default="equity", max_length=64)
    side: str = Field(min_length=1, max_length=16)
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: Decimal
    exit_price: Decimal | None = None
    quantity: Decimal
    fees: Decimal = Decimal("0")
    pnl_amount: Decimal | None = None
    pnl_r: Decimal | None = None
    strategy_version_id: UUID | None = None
    setup_id: UUID | None = None
    timeframe: str | None = None
    session: str | None = None
    market_regime_id: UUID | None = None
    planned_risk_amount: Decimal | None = None
    actual_risk_amount: Decimal | None = None
    rule_adherence_score: Decimal | None = None
    emotional_state_before: str | None = None
    emotional_state_after: str | None = None
    journal_summary: str | None = None
    metadata: dict = Field(default_factory=dict)


class TradeRead(ApiModel):
    id: UUID
    symbol: str
    asset_class: str
    side: str
    entry_time: datetime
    exit_time: datetime | None
    entry_price: Decimal
    exit_price: Decimal | None
    quantity: Decimal
    fees: Decimal
    pnl_amount: Decimal | None
    pnl_r: Decimal | None
    strategy_version_id: UUID | None
    setup_id: UUID | None
    timeframe: str | None
    session: str | None
    market_regime_id: UUID | None
    planned_risk_amount: Decimal | None
    actual_risk_amount: Decimal | None
    rule_adherence_score: Decimal | None
    emotional_state_before: str | None
    emotional_state_after: str | None
    journal_summary: str | None
    metadata: dict
    created_at: datetime
    updated_at: datetime


class TradeRecommendationRead(BaseModel):
    id: str
    title: str
    action: str
    strategy: str | None = None
    setup: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    technical_tags: list[str] = Field(default_factory=list)
    rationale: str
    risk_notes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
