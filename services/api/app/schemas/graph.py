from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import ApiModel


class TaxonomyItemCreate(BaseModel):
    taxonomy_type: str = Field(min_length=1, max_length=80)
    slug: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    description: str | None = None
    is_core: bool = False
    properties: dict = Field(default_factory=dict)


class TaxonomyItemRead(ApiModel):
    id: UUID
    taxonomy_type: str
    slug: str
    label: str
    description: str | None
    is_core: bool
    properties: dict
    created_at: datetime
    updated_at: datetime


class KgNodeCreate(BaseModel):
    node_type: str = Field(min_length=1, max_length=80)
    source_table: str | None = None
    source_id: UUID | None = None
    label: str = Field(min_length=1, max_length=240)
    properties: dict = Field(default_factory=dict)
    confidence: Decimal | None = None
    created_by: str = Field(default="system", max_length=80)


class KgNodeRead(ApiModel):
    id: UUID
    node_type: str
    source_table: str | None
    source_id: UUID | None
    label: str
    properties: dict
    confidence: Decimal | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class KgEdgeCreate(BaseModel):
    edge_type: str = Field(min_length=1, max_length=80)
    from_node_id: UUID
    to_node_id: UUID
    properties: dict = Field(default_factory=dict)
    confidence: Decimal | None = None
    evidence_chunk_ids: list[UUID] = Field(default_factory=list)
    created_by: str = Field(default="system", max_length=80)


class KgEdgeRead(ApiModel):
    id: UUID
    edge_type: str
    from_node_id: UUID
    to_node_id: UUID
    properties: dict
    confidence: Decimal | None
    evidence_chunk_ids: list[UUID]
    created_by: str
    created_at: datetime


class GraphEvidenceRead(BaseModel):
    chunk_id: UUID
    source_document_id: UUID | None = None
    source_title: str
    text: str


class GraphNeighborhoodNodeRead(BaseModel):
    id: UUID
    label: str
    node_type: str
    confidence: Decimal | None
    properties: dict[str, Any] = Field(default_factory=dict)
    open_conflict_count: int = 0


class GraphNeighborhoodEdgeRead(BaseModel):
    id: UUID
    edge_type: str
    from_node_id: UUID
    to_node_id: UUID
    confidence: Decimal | None
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence_chunk_ids: list[UUID] = Field(default_factory=list)
    evidence_count: int = 0
    contributing_sources: list[str] = Field(default_factory=list)
    evidence: list[GraphEvidenceRead] = Field(default_factory=list)


class GraphNeighborhoodRead(BaseModel):
    root_id: UUID
    depth: int
    nodes: list[GraphNeighborhoodNodeRead] = Field(default_factory=list)
    edges: list[GraphNeighborhoodEdgeRead] = Field(default_factory=list)
