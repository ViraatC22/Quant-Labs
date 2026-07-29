"""Retrieval over trading memory: text (vector + keyword), graph, and claims.

Vector search is brute-force cosine in Python so it is dialect-portable
(identical on SQLite dev and PostgreSQL) and fully testable without pgvector.
At personal scale (thousands of chunks) this is fine; the HNSW index and a
native ``<=>`` query path are the documented escape hatch for larger corpora.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Claim, ClaimEvidence, KgEdge, KgNode, MemoryChunk, Trade
from app.services import embeddings

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "for",
    "and", "or", "how", "what", "which", "does", "do", "with", "my", "me", "i",
    "when", "where", "why", "that", "this", "it", "as", "at", "by", "be",
    "did", "we", "trade", "trades", "our",
    "after", "already", "should", "have", "has", "had", "from", "about", "say",
}


@dataclass
class RetrievedChunk:
    chunk_id: UUID
    source_id: UUID
    source_title: str
    text: str
    score: float


@dataclass
class RetrievedClaim:
    claim_id: UUID
    statement_text: str
    polarity: str
    predicate: str
    object_literal: str | None
    source_titles: list[str]
    score: float


@dataclass
class RetrievedTrade:
    trade_id: UUID
    symbol: str
    asset_class: str
    side: str
    entry_time: datetime
    exit_time: datetime | None
    entry_price: float
    exit_price: float | None
    quantity: float
    contract_multiplier: float
    fees: float
    pnl_amount: float | None
    pnl_r: float | None
    timeframe: str | None
    session: str | None
    planned_risk_amount: float | None
    actual_risk_amount: float | None
    rule_adherence_score: float | None
    emotional_state_before: str | None
    emotional_state_after: str | None
    journal_summary: str | None
    strategy: str | None
    setup: str | None
    score: float


@dataclass
class RetrievedGraph:
    nodes: list[KgNode] = field(default_factory=list)
    edges: list[KgEdge] = field(default_factory=list)


def query_tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


# --- text retrieval --------------------------------------------------------


def search_chunks(
    db: Session, *, user_id: UUID, query: str, limit: int = 6
) -> list[RetrievedChunk]:
    """Hybrid vector + keyword search over memory chunks via reciprocal-rank
    fusion, so a chunk strong on either signal surfaces."""
    chunks = db.scalars(
        select(MemoryChunk).where(MemoryChunk.user_id == user_id)
    ).all()
    if not chunks:
        return []

    query_embedding = embeddings.embed_text(query)
    tokens = set(query_tokens(query))

    vector_ranked: list[tuple[MemoryChunk, float]] = []
    if query_embedding is not None:
        scored = [
            (chunk, embeddings.cosine_similarity(query_embedding, chunk.embedding))
            for chunk in chunks
            if chunk.embedding
        ]
        # Very low positive cosine scores are numerical noise. Feeding every
        # positive vector into RRF made unrelated papers look authoritative.
        vector_ranked = sorted(
            (item for item in scored if item[1] >= 0.2),
            key=lambda item: item[1],
            reverse=True,
        )

    keyword_ranked = sorted(
        (
            (chunk, score)
            for chunk in chunks
            if _meaningful_keyword_overlap(
                score := _keyword_overlap(_chunk_searchable_text(chunk), tokens), tokens
            )
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    fused = _rrf([vector_ranked, keyword_ranked])
    results: list[RetrievedChunk] = []
    for chunk, score in fused[:limit]:
        if score <= 0:
            continue
        metadata = chunk.chunk_metadata or {}
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                source_id=chunk.source_id,
                source_title=metadata.get("source_title", "source"),
                text=chunk.text,
                score=round(score, 4),
            )
        )
    return results


def _keyword_overlap(text: str, query_tokens_set: set[str]) -> float:
    if not query_tokens_set:
        return 0.0
    text_tokens = set(_TOKEN_RE.findall(text.lower()))
    if not text_tokens:
        return 0.0
    return len(query_tokens_set & text_tokens) / len(query_tokens_set)


def _chunk_searchable_text(chunk: MemoryChunk) -> str:
    metadata = chunk.chunk_metadata or {}
    return f"{metadata.get('source_title', '')} {chunk.text}"


def _meaningful_keyword_overlap(score: float, query_tokens_set: set[str]) -> bool:
    if not query_tokens_set or score <= 0:
        return False
    matches = round(score * len(query_tokens_set))
    return matches >= (1 if len(query_tokens_set) <= 3 else 2)


def _rrf(rankings: list[list[tuple[MemoryChunk, float]]], k: int = 60):
    """Reciprocal-rank fusion. Only positively-scored entries contribute."""
    scores: dict[UUID, float] = {}
    objects: dict[UUID, MemoryChunk] = {}
    for ranking in rankings:
        for rank, (chunk, raw) in enumerate(ranking):
            if raw <= 0:
                continue
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)
            objects[chunk.id] = chunk
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [(objects[cid], score) for cid, score in ordered]


# --- claim retrieval -------------------------------------------------------


def search_claims(
    db: Session, *, user_id: UUID, query: str, limit: int = 6
) -> list[RetrievedClaim]:
    claims = db.scalars(select(Claim).where(Claim.user_id == user_id)).all()
    if not claims:
        return []
    query_embedding = embeddings.embed_text(query)
    tokens = set(query_tokens(query))

    scored: list[tuple[Claim, float]] = []
    for claim in claims:
        vector_score = (
            embeddings.cosine_similarity(query_embedding, claim.embedding)
            if query_embedding and claim.embedding
            else 0.0
        )
        keyword_score = _keyword_overlap(claim.statement_text, tokens)
        combined = 0.6 * vector_score + 0.4 * keyword_score
        if _meaningful_keyword_overlap(keyword_score, tokens) or vector_score >= 0.2:
            scored.append((claim, combined))
    scored.sort(key=lambda item: item[1], reverse=True)

    results: list[RetrievedClaim] = []
    for claim, score in scored[:limit]:
        source_titles = _claim_source_titles(db, claim.id)
        results.append(
            RetrievedClaim(
                claim_id=claim.id,
                statement_text=claim.statement_text,
                polarity=claim.polarity,
                predicate=claim.predicate,
                object_literal=claim.object_literal,
                source_titles=source_titles,
                score=round(score, 4),
            )
        )
    return results


# --- trade retrieval ------------------------------------------------------


def search_trades(
    db: Session, *, user_id: UUID, query: str, limit: int = 4
) -> list[RetrievedTrade]:
    """Rank the user's journaled trades by symbol, intent, and note overlap.

    Loss-review questions deliberately boost losing rows, so a winning trade in
    the same symbol cannot crowd out the record the user is asking about.
    """
    trades = db.scalars(select(Trade).where(Trade.user_id == user_id)).all()
    if not trades:
        return []

    lowered = query.lower()
    tokens = set(query_tokens(query))
    loss_intent = bool(re.search(r"\b(lose|losing|lost|loss|went wrong|failed)\b", lowered))
    win_intent = bool(re.search(r"\b(win|winning|won|winner|worked)\b", lowered))
    scored: list[tuple[Trade, float]] = []

    for trade in trades:
        metadata = trade.trade_metadata or {}
        strategy = _metadata_text(metadata, "strategy", "strategy_name", "strategyName")
        setup = _metadata_text(metadata, "setup", "setup_name", "setupName")
        searchable = " ".join(
            part
            for part in (
                trade.symbol,
                trade.asset_class,
                trade.side,
                trade.timeframe,
                trade.session,
                trade.emotional_state_before,
                trade.emotional_state_after,
                trade.journal_summary,
                strategy,
                setup,
            )
            if part
        )
        trade_tokens = set(_TOKEN_RE.findall(searchable.lower()))
        overlap = len(tokens & trade_tokens) / len(tokens) if tokens else 0.0
        symbol_match = trade.symbol.lower() in tokens
        pnl = float(trade.pnl_amount) if trade.pnl_amount is not None else None

        score = overlap * 2.0
        if symbol_match:
            score += 4.0
        if loss_intent and pnl is not None:
            score += 3.0 if pnl < 0 else -1.5
        if win_intent and pnl is not None:
            score += 3.0 if pnl > 0 else -1.5

        # A specific symbol, a meaningful journal overlap, or matching outcome
        # intent is required. Generic unrelated rows should never be evidence.
        outcome_match = (loss_intent and pnl is not None and pnl < 0) or (
            win_intent and pnl is not None and pnl > 0
        )
        if symbol_match or overlap > 0 or outcome_match:
            scored.append((trade, score))

    scored.sort(
        key=lambda item: (item[1], item[0].entry_time),
        reverse=True,
    )
    return [_to_retrieved_trade(trade, score) for trade, score in scored[:limit]]


def _to_retrieved_trade(trade: Trade, score: float) -> RetrievedTrade:
    metadata = trade.trade_metadata or {}
    return RetrievedTrade(
        trade_id=trade.id,
        symbol=trade.symbol,
        asset_class=trade.asset_class,
        side=trade.side,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        entry_price=float(trade.entry_price),
        exit_price=float(trade.exit_price) if trade.exit_price is not None else None,
        quantity=float(trade.quantity),
        contract_multiplier=float(trade.contract_multiplier),
        fees=float(trade.fees),
        pnl_amount=float(trade.pnl_amount) if trade.pnl_amount is not None else None,
        pnl_r=float(trade.pnl_r) if trade.pnl_r is not None else None,
        timeframe=trade.timeframe,
        session=trade.session,
        planned_risk_amount=(
            float(trade.planned_risk_amount) if trade.planned_risk_amount is not None else None
        ),
        actual_risk_amount=(
            float(trade.actual_risk_amount) if trade.actual_risk_amount is not None else None
        ),
        rule_adherence_score=(
            float(trade.rule_adherence_score) if trade.rule_adherence_score is not None else None
        ),
        emotional_state_before=trade.emotional_state_before,
        emotional_state_after=trade.emotional_state_after,
        journal_summary=trade.journal_summary,
        strategy=_metadata_text(metadata, "strategy", "strategy_name", "strategyName"),
        setup=_metadata_text(metadata, "setup", "setup_name", "setupName"),
        score=round(score, 4),
    )


def _metadata_text(metadata: dict, *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _claim_source_titles(db: Session, claim_id: UUID) -> list[str]:
    doc_ids = db.scalars(
        select(ClaimEvidence.source_document_id).where(ClaimEvidence.claim_id == claim_id)
    ).all()
    if not doc_ids:
        return []
    from app.models.domain import SourceDocument

    titles = db.scalars(
        select(SourceDocument.title).where(SourceDocument.id.in_(doc_ids))
    ).all()
    return sorted(set(titles))


# --- graph retrieval -------------------------------------------------------


def link_entities(db: Session, *, user_id: UUID, query: str, limit: int = 5) -> list[KgNode]:
    """Map question terms to graph nodes by label-embedding similarity + token
    overlap on the label."""
    nodes = db.scalars(select(KgNode).where(KgNode.user_id == user_id)).all()
    if not nodes:
        return []
    query_embedding = embeddings.embed_text(query)
    tokens = set(query_tokens(query))
    scored: list[tuple[KgNode, float]] = []
    for node in nodes:
        vector_score = (
            embeddings.cosine_similarity(query_embedding, node.label_embedding)
            if query_embedding and node.label_embedding
            else 0.0
        )
        label_tokens = set(_TOKEN_RE.findall(node.label.lower()))
        overlap = len(tokens & label_tokens) / len(tokens) if tokens else 0.0
        combined = max(vector_score, overlap)
        if combined > 0.2:
            scored.append((node, combined))
    scored.sort(key=lambda item: item[1], reverse=True)
    return [node for node, _ in scored[:limit]]


def neighborhood(
    db: Session, *, user_id: UUID, node_ids: list[UUID], depth: int = 1
) -> RetrievedGraph:
    """Expand a k-hop neighborhood around ``node_ids`` (depth ≤ 3)."""
    depth = max(1, min(depth, 3))
    visited: set[UUID] = set(node_ids)
    frontier: set[UUID] = set(node_ids)
    edges: dict[UUID, KgEdge] = {}
    for _ in range(depth):
        if not frontier:
            break
        hop_edges = db.scalars(
            select(KgEdge).where(
                KgEdge.user_id == user_id,
                KgEdge.from_node_id.in_(frontier) | KgEdge.to_node_id.in_(frontier),
            )
        ).all()
        next_frontier: set[UUID] = set()
        for edge in hop_edges:
            edges[edge.id] = edge
            for endpoint in (edge.from_node_id, edge.to_node_id):
                if endpoint not in visited:
                    visited.add(endpoint)
                    next_frontier.add(endpoint)
        frontier = next_frontier
    nodes = (
        db.scalars(select(KgNode).where(KgNode.id.in_(visited))).all() if visited else []
    )
    return RetrievedGraph(nodes=list(nodes), edges=list(edges.values()))
