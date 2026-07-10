"""Retrieval over trading memory: text (vector + keyword), graph, and claims.

Vector search is brute-force cosine in Python so it is dialect-portable
(identical on SQLite dev and PostgreSQL) and fully testable without pgvector.
At personal scale (thousands of chunks) this is fine; the HNSW index and a
native ``<=>`` query path are the documented escape hatch for larger corpora.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain import Claim, ClaimEvidence, KgEdge, KgNode, MemoryChunk
from app.services import embeddings

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "for",
    "and", "or", "how", "what", "which", "does", "do", "with", "my", "me", "i",
    "when", "where", "why", "that", "this", "it", "as", "at", "by", "be",
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
        vector_ranked = sorted(scored, key=lambda item: item[1], reverse=True)

    keyword_ranked = sorted(
        ((chunk, _keyword_overlap(chunk.text, tokens)) for chunk in chunks),
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
        if combined > 0:
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
