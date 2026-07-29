from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class SourceDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    document_type: str = Field(default="note", max_length=80)
    uri: str | None = None
    content_text: str | None = None
    metadata: dict = Field(default_factory=dict)


class SourceDocumentRead(ApiModel):
    id: UUID
    title: str
    document_type: str
    uri: str | None
    content_text: str | None
    metadata: dict
    created_at: datetime
    updated_at: datetime


class SourceDocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    document_type: str | None = Field(default=None, max_length=80)
    content_text: str | None = None
    metadata: dict | None = None


class VaultUrlImportRequest(BaseModel):
    url: str = Field(min_length=1)


class StrategyInfo(BaseModel):
    name: str | None = None
    summary: str | None = None
    setup: str | None = None
    entry_rules: list[str] = Field(default_factory=list)
    exit_rules: list[str] = Field(default_factory=list)
    risk_rules: list[str] = Field(default_factory=list)
    timeframe: str | None = None
    indicators: list[str] = Field(default_factory=list)
    market: str | None = None
    technical_tags: list[str] = Field(default_factory=list)
    technical_profile: dict[str, list[str]] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class VaultImportRead(BaseModel):
    title: str
    kind: str
    source: str
    body: str
    tags: list[str] = Field(default_factory=list)
    ai_tags: list[str] = Field(default_factory=list)
    strategy_info: StrategyInfo | None = None
    metadata: dict = Field(default_factory=dict)


class AiProviderStatus(BaseModel):
    id: str
    label: str
    configured: bool
    model: str
    priority: int
    protocol: str
    cooldown_remaining_seconds: int = 0


class AiRouterStatus(BaseModel):
    mode: str
    active_provider_id: str | None = None
    research_mode: str = "local"
    research_active_provider_id: str | None = None
    providers: list[AiProviderStatus] = Field(default_factory=list)


class AiProviderSelfTest(BaseModel):
    id: str
    label: str
    configured: bool
    ok: bool
    latency_ms: int | None = None
    error: str | None = None


class AiSelfTestResult(BaseModel):
    mode: str
    providers: list[AiProviderSelfTest] = Field(default_factory=list)


class JournalEntryCreate(BaseModel):
    entry_date: date
    title: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1)
    emotional_state: str | None = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class JournalEntryUpdate(BaseModel):
    entry_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=240)
    body: str | None = Field(default=None, min_length=1)
    emotional_state: str | None = Field(default=None, max_length=120)
    tags: list[str] | None = None
    metadata: dict | None = None


class JournalEntryRead(ApiModel):
    id: UUID
    entry_date: date
    title: str
    body: str
    emotional_state: str | None
    tags: list[str]
    metadata: dict
    created_at: datetime
    updated_at: datetime
