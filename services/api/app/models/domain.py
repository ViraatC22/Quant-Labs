from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.core.config import settings
from app.db.base import Base
from app.db.types import GUID, GUIDArray, JSONType


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_kw: object) -> str:
        return f"vector({self.dimensions})"


# pgvector column on PostgreSQL; JSON array of floats on SQLite (dev/test).
# Dimension follows the configured embedding provider so the ORM, the migration,
# and the vectors actually written all agree.
def _embedding_column(dimensions: int | None = None):
    dims = dimensions if dimensions is not None else settings.embedding_dim
    return JSON().with_variant(Vector(dims), "postgresql")


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
    # Contract/point multiplier (options control 100 shares, futures vary by
    # symbol). P&L must include this or non-equity trades are computed wrong.
    contract_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=1, nullable=False, server_default="1"
    )
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
    # Embedding of "label (node_type)" — powers entity resolution: a new entity
    # is matched against existing ones by cosine similarity so "FVG" and "fair
    # value gap" collapse to one node instead of two.
    label_embedding: Mapped[list[float] | None] = mapped_column(_embedding_column())
    created_by: Mapped[str] = mapped_column(String(80), default="system", nullable=False)

    __table_args__ = (
        # Concept nodes (tag/strategy/setup/indicator/rule/…) dedupe by label.
        # Source nodes carry a source_id and are naturally unique per document,
        # so the constraint is partial to avoid title collisions across docs.
        Index(
            "kg_nodes_concept_unique",
            "user_id",
            "node_type",
            "label",
            unique=True,
            sqlite_where=text("source_id IS NULL"),
            postgresql_where=text("source_id IS NULL"),
        ),
    )


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

    __table_args__ = (
        Index(
            "kg_edges_triple_unique",
            "user_id",
            "edge_type",
            "from_node_id",
            "to_node_id",
            unique=True,
        ),
    )


class Claim(TimestampMixin, Base):
    """An atomic factual statement extracted from a source and linked to the
    graph and its evidence. This is the primitive that powers trust scoring,
    conflict detection, source monitoring, and the temporal claim view."""

    __tablename__ = "claims"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), index=True, nullable=False)
    workspace_id: Mapped[UUID | None] = mapped_column(GUID())
    subject_node_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("kg_nodes.id"), nullable=False, index=True
    )
    predicate: Mapped[str] = mapped_column(String(120), nullable=False)
    object_node_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("kg_nodes.id"))
    object_literal: Mapped[str | None] = mapped_column(Text)
    statement_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(_embedding_column())
    # "supports" | "refutes" | "neutral" — the polarity of the assertion, used
    # with subject+predicate to detect contradictions.
    polarity: Mapped[str] = mapped_column(String(16), default="neutral", nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_by: Mapped[str] = mapped_column(String(80), default="claim_extraction", nullable=False)

    __table_args__ = (
        # Polarity is part of identity: (ORB, works_in, chop, supports) and
        # (…, refutes) are DIFFERENT claims that coexist so conflict detection
        # can pair them. Re-importing the same source hits the same tuple and
        # upserts (replay-safe), while multiple sources agreeing add evidence
        # rows to the one claim.
        Index(
            "claims_natural_unique",
            "user_id",
            "subject_node_id",
            "predicate",
            "object_literal",
            "polarity",
            unique=True,
        ),
    )


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("claims.id"), nullable=False, index=True
    )
    source_document_id: Mapped[UUID] = mapped_column(GUID(), nullable=False)
    chunk_id: Mapped[UUID | None] = mapped_column(GUID())
    stance: Mapped[str] = mapped_column(String(16), default="supports", nullable=False)
    quote: Mapped[str | None] = mapped_column(Text)
    # When the source asserted the claim — powers the temporal "support over
    # time" view. Distinct from created_at (when we ingested it).
    asserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ClaimConflict(Base):
    __tablename__ = "claim_conflicts"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), index=True, nullable=False)
    claim_a_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("claims.id"), nullable=False)
    claim_b_id: Mapped[UUID] = mapped_column(GUID(), ForeignKey("claims.id"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # "open" | "resolved" | "dismissed"
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    resolution_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("claim_conflicts_pair_unique", "user_id", "claim_a_id", "claim_b_id", unique=True),
    )


class ResearchConversation(Base):
    __tablename__ = "research_conversations"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(GUID(), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str] = mapped_column(String(32), nullable=False)
    answer_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    trust_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    payload: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
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
    embedding: Mapped[list[float] | None] = mapped_column(_embedding_column())
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)
    token_count: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
