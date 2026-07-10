from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class ResearchAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class CitationRead(BaseModel):
    ref: str
    kind: str
    source_title: str
    snippet: str


class ResearchAnswerRead(BaseModel):
    question: str
    route: str
    answer_markdown: str
    trust_score: float
    citations: list[CitationRead] = Field(default_factory=list)
    special_elements: list[dict[str, Any]] = Field(default_factory=list)
    retrieved: dict[str, Any] = Field(default_factory=dict)


class ConversationRead(ApiModel):
    id: UUID
    question: str
    route: str
    answer_markdown: str
    trust_score: Decimal | None
    created_at: datetime


class SearchResultRead(BaseModel):
    chunk_id: UUID
    source_id: UUID
    source_title: str
    text: str
    score: float


class ClaimRead(ApiModel):
    id: UUID
    subject_node_id: UUID
    predicate: str
    object_literal: str | None
    statement_text: str
    polarity: str
    confidence: Decimal | None
    created_at: datetime


class ClaimConflictRead(BaseModel):
    id: UUID
    status: str
    detected_at: datetime
    claim_a: ClaimRead
    claim_b: ClaimRead


class ClaimTimelinePoint(BaseModel):
    asserted_at: datetime
    stance: str
    source_document_id: UUID
    quote: str | None


class ConflictResolveRequest(BaseModel):
    status: str = Field(pattern="^(open|resolved|dismissed)$")
    resolution_note: str | None = None
