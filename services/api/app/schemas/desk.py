"""Response models for the session desk (dashboard, macro desk, news, sessions)."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class NewsItemRead(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime | None = None
    age_label: str | None = None
    summary: str | None = None
    image_url: str | None = None
    symbol: str | None = None


class BiasSignalRead(BaseModel):
    label: str
    # "bullish"/"bearish"/"neutral" for directional signals;
    # "confirming"/"undercutting"/"neutral" for confirmation signals.
    direction: str
    value: float
    weight: float
    detail: str
    # "directional" signals vote on the call; "confirmation" signals only
    # adjust confidence in it.
    role: str


class InstrumentBiasRead(BaseModel):
    symbol: str
    # fx | index | commodity | crypto | equity — descriptive grouping only;
    # the bias engine itself is asset-class agnostic.
    asset_class: str = "equity"
    direction: str
    # Integer percent, capped at bias.MAX_CONFIDENCE. This is a measure of how
    # well-supported the directional reading is, NOT a probability that the move
    # continues, and it is computed rather than model-asserted.
    confidence: int = Field(ge=0, le=100)
    strength: float
    agreement: float
    coverage: float
    last_price: float
    change_percent: float
    signals: list[BiasSignalRead] = Field(default_factory=list)
    explanation: str
    # "derived" (deterministic text) or "model" (a provider rephrased the same
    # computed facts). Never a source of new claims either way.
    explanation_mode: str
    as_of: str
    provider: str
    price_basis: str
    sample_size: int
    delayed: bool
    stale: bool
    proxy_note: str | None = None
    limitations: list[str] = Field(default_factory=list)
    writer_provider_id: str | None = None
    writer_model: str | None = None
    # Retrieved headlines for this instrument (data, not prose). Empty without
    # an FMP key or when the provider has no coverage for the symbol.
    news: list[NewsItemRead] = Field(default_factory=list)
    # --- Calibration (learning from the graded record) --------------------
    # `confidence` above is the value to display. When calibration is active it
    # is the blended number; `raw_confidence` always carries the engine output,
    # and `calibration_note` says what the adjustment rests on.
    raw_confidence: int = Field(ge=0, le=100, default=0)
    calibration_applied: bool = False
    calibration_sample: int = 0
    calibration_note: str = ""


class MacroDeskRead(BaseModel):
    instruments: list[InstrumentBiasRead] = Field(default_factory=list)
    # Symbols whose context could not be loaded, with the reason. Reported
    # explicitly so a missing instrument is visible rather than just absent.
    unavailable: dict[str, str] = Field(default_factory=dict)
    generated_at: datetime


class SessionStateRead(BaseModel):
    key: str
    label: str
    timezone: str
    phase: str
    phase_label: str
    local_time: str
    is_open: bool
    next_phase: str
    next_phase_label: str
    next_transition_at: datetime
    seconds_to_next: int
    countdown: str


class SessionsRead(BaseModel):
    sessions: list[SessionStateRead] = Field(default_factory=list)
    now_utc: datetime


class NewsFeedRead(BaseModel):
    items: list[NewsItemRead] = Field(default_factory=list)
    available: bool
    stale: bool = False
    reason: str | None = None
    provider: str


class CalendarEventRead(BaseModel):
    title: str
    currency: str
    # high | medium | low | holiday | unknown
    impact: str
    # Null for all-day and tentative events, which carry a date but no time.
    scheduled_at: datetime | None = None
    date_label: str
    all_day: bool = False
    tentative: bool = False
    forecast: str | None = None
    previous: str | None = None
    actual: str | None = None
    url: str | None = None


class CalendarRead(BaseModel):
    events: list[CalendarEventRead] = Field(default_factory=list)
    available: bool
    stale: bool = False
    reason: str | None = None
    source: str
    now_utc: datetime


class CurrencyStrengthRead(BaseModel):
    currency: str
    score: float
    # Number of pairs behind the score. A single pair is not a strength reading.
    pairs: int
    contributions: list[tuple[str, float]] = Field(default_factory=list)


class FlowEntryRead(BaseModel):
    symbol: str
    change_percent: float
    asset_class: str = "equity"


class StrengthRead(BaseModel):
    currencies: list[CurrencyStrengthRead] = Field(default_factory=list)
    flow: list[FlowEntryRead] = Field(default_factory=list)
    unavailable: dict[str, str] = Field(default_factory=dict)
    window: str
    generated_at: datetime


class CalibrationBucketRead(BaseModel):
    bucket: str
    graded: int
    correct: int
    hit_rate: float | None = None


class CalibrationRead(BaseModel):
    buckets: list[CalibrationBucketRead] = Field(default_factory=list)
    # Share of graded directional windows whose move exceeded the flat band.
    decisive_share: float | None = None
    # What a coin-flip direction call would have scored on the same windows.
    # A hit rate must beat this before it means anything.
    luck_baseline: float | None = None
    total_graded: int = 0
    min_sample: int
    generated_at: datetime


class MoodComponentRead(BaseModel):
    symbol: str
    label: str
    # "risk" | "haven"
    role: str
    change_percent: float
    # Positive pushes the read toward risk-on, negative toward risk-off.
    contribution: float


class MarketMoodRead(BaseModel):
    # risk_on | risk_off | mixed
    mood: str
    spread: float
    risk_score: float
    haven_score: float
    components: list[MoodComponentRead] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)
    summary: str
    caveat: str
    generated_at: datetime


class DeskReportRead(BaseModel):
    id: UUID
    report_date: date
    title: str
    # Sections: graded_calls, instruments, events, strength, sessions,
    # unavailable, caveats, assets_analyzed. Stored at generation time so the
    # archive is a record of what the desk said, not a regeneration.
    payload: dict[str, Any] = Field(default_factory=dict)
    read_at: datetime | None = None
    created_at: datetime


class DeskReportSummaryRead(BaseModel):
    id: UUID
    report_date: date
    title: str
    read_at: datetime | None = None
    created_at: datetime
    assets_analyzed: int = 0
    high_impact_events: int = 0


class BriefingItemRead(BaseModel):
    symbol: str
    direction: str
    confidence: int
    band: str
    text: str
    as_of: str


class BriefingRead(BaseModel):
    headline: str
    summary: str
    regime: str
    tone: str
    items: list[BriefingItemRead] = Field(default_factory=list)
    generated_at: datetime
    caveats: list[str] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
