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


class VaultUrlImportRequest(BaseModel):
    url: str = Field(min_length=1)


class VaultImportRead(BaseModel):
    title: str
    kind: str
    source: str
    body: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class JournalEntryCreate(BaseModel):
    entry_date: date
    title: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1)
    emotional_state: str | None = Field(default=None, max_length=120)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


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
