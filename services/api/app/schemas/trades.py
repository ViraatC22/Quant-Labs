from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import AssetClass, TradeSide
from app.schemas.common import ApiModel


class TradeCreate(BaseModel):
    id: UUID | None = None  # client may supply a UUID for idempotent offline replay
    symbol: str = Field(min_length=1, max_length=32)
    asset_class: AssetClass = AssetClass.equity
    side: TradeSide
    entry_time: datetime
    exit_time: datetime | None = None
    entry_price: Decimal
    exit_price: Decimal | None = None
    quantity: Decimal = Field(gt=0)
    contract_multiplier: Decimal = Field(default=Decimal("1"), gt=0)
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


class TradeUpdate(BaseModel):
    exit_time: datetime | None = None
    exit_price: Decimal | None = None
    contract_multiplier: Decimal | None = Field(default=None, gt=0)
    fees: Decimal | None = None
    pnl_amount: Decimal | None = None
    pnl_r: Decimal | None = None
    emotional_state_after: str | None = None
    journal_summary: str | None = None
    metadata: dict | None = None


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
    contract_multiplier: Decimal
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
    draft: dict = Field(default_factory=dict)


class MarketQuoteRead(BaseModel):
    symbol: str
    provider_symbol: str
    provider: str
    last_price: Decimal
    previous_close: Decimal | None = None
    currency: str | None = None
    market_time: datetime | None = None
    delayed: bool = True
    stale: bool = False
    bid: Decimal | None = None
    ask: Decimal | None = None
    spread: Decimal | None = None
    # See market_data.PRICE_BASIS_*. Clients sizing real orders must branch on
    # `executable` rather than reading `last_price` as a fill price.
    price_basis: str
    executable: bool = False
    proxy_note: str | None = None


class MarketContextRead(BaseModel):
    symbol: str
    provider_symbol: str
    provider: str
    interval: str
    lookback: str
    as_of: datetime
    delayed: bool = True
    stale: bool = False
    sample_size: int
    last_price: float
    change_percent: float
    rsi_14: float | None = None
    atr_percent: float | None = None
    bollinger_width_percent: float | None = None
    volume_percentile: float | None = None
    trend_efficiency: float | None = None
    flow: str
    bearing: str
    pulse: str
    confidence: float = Field(ge=0.0, le=1.0)
    limitations: list[str] = Field(default_factory=list)
    price_basis: str
    proxy_note: str | None = None


class StrategyEvaluationRequest(BaseModel):
    idea: str = Field(min_length=8, max_length=6000)
    symbol: str | None = Field(default=None, max_length=32)
    save_journal: bool = True


class StrategyEvaluationRead(BaseModel):
    title: str
    decision: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    technical_tags: list[str] = Field(default_factory=list)
    technical_profile: dict[str, list[str]] = Field(default_factory=dict)
    included: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)
    draft: dict = Field(default_factory=dict)
    journal_entry_id: UUID | None = None
