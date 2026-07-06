from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.db.base import Base
from app.db.types import GUID, GUIDArray, JSONType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_kw: object) -> str:
        return f"vector({self.dimensions})"


# pgvector column on PostgreSQL; JSON array of floats on SQLite (dev/test).
def _embedding_column(dimensions: int):
    return JSON().with_variant(Vector(dimensions), "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(160))


class SourceDocument(TimestampMixin, Base):
    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    document_type: Mapped[str] = mapped_column(String(80), nullable=False, default="note")
    uri: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONType, default=dict, nullable=False
    )


class JournalEntry(TimestampMixin, Base):
    __tablename__ = "journal_entries"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), index=True, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    emotional_state: Mapped[str | None] = mapped_column(String(120))
    tags: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    journal_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONType, default=dict, nullable=False
    )


class Trade(TimestampMixin, Base):
    __tablename__ = "trades"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    asset_class: Mapped[str] = mapped_column(String(64), nullable=False, default="equity")
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    pnl_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    pnl_r: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    strategy_version_id: Mapped[UUID | None] = mapped_column(GUID())
    setup_id: Mapped[UUID | None] = mapped_column(GUID())
    timeframe: Mapped[str | None] = mapped_column(String(32))
    session: Mapped[str | None] = mapped_column(String(80))
    market_regime_id: Mapped[UUID | None] = mapped_column(GUID())
    planned_risk_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    actual_risk_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    rule_adherence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    emotional_state_before: Mapped[str | None] = mapped_column(String(120))
    emotional_state_after: Mapped[str | None] = mapped_column(String(120))
    journal_summary: Mapped[str | None] = mapped_column(Text)
    trade_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)


class TaxonomyItem(TimestampMixin, Base):
    __tablename__ = "taxonomy_items"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), index=True, nullable=False)
    taxonomy_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_core: Mapped[bool] = mapped_column(default=False, nullable=False)
    properties: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)


class KgNode(TimestampMixin, Base):
    __tablename__ = "kg_nodes"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), index=True, nullable=False)
    node_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_table: Mapped[str | None] = mapped_column(String(120))
    source_id: Mapped[UUID | None] = mapped_column(GUID())
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    properties: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_by: Mapped[str] = mapped_column(String(80), default="system", nullable=False)


class KgEdge(Base):
    __tablename__ = "kg_edges"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), index=True, nullable=False)
    edge_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    from_node_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("kg_nodes.id"), nullable=False, index=True
    )
    to_node_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("kg_nodes.id"), nullable=False, index=True
    )
    properties: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    evidence_chunk_ids: Mapped[list[UUID]] = mapped_column(
        GUIDArray(), default=list, nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(80), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MemoryChunk(Base):
    __tablename__ = "memory_chunks"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_id: Mapped[UUID] = mapped_column(GUID(), nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(_embedding_column(1536))
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)
    token_count: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
