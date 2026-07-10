"""Embedding-similarity entity resolution (Lattice L3).

When source learning is about to create a concept node, it first asks here
whether an existing node of the same type is the *same entity* under a
different surface form ("FVG" vs "fair value gap"). Exact-label matches are
handled by the caller's get-or-create; this adds the fuzzy layer:

- cosine ≥ entity_match_threshold        → same entity, reuse the existing node
- entity_review_threshold ≤ cosine < match → possible duplicate, reuse the
  existing node but record a `possible_duplicate_of` marker for later review
- cosine < entity_review_threshold       → genuinely new, create a node

The label embedding is stored on the node so future resolutions compare against
it directly instead of re-embedding every candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import KgNode
from app.services import embeddings


@dataclass(frozen=True)
class ResolutionResult:
    node: KgNode | None
    similarity: float
    is_possible_duplicate: bool


def embed_label(label: str, node_type: str) -> list[float] | None:
    """Embed a node so it can be matched. Type is included so a 'london'
    timeframe and a 'london' market don't collapse into one node."""
    return embeddings.embed_text(f"{label} ({node_type})")


def resolve_entity(
    db: Session,
    *,
    user_id: UUID,
    node_type: str,
    label: str,
    label_embedding: list[float] | None = None,
) -> ResolutionResult:
    """Find the best existing node for ``label`` of ``node_type`` for this user."""
    query_embedding = label_embedding or embed_label(label, node_type)
    if query_embedding is None:
        return ResolutionResult(node=None, similarity=0.0, is_possible_duplicate=False)

    candidates = db.scalars(
        select(KgNode).where(
            KgNode.user_id == user_id,
            KgNode.node_type == node_type,
            KgNode.source_id.is_(None),
        )
    ).all()

    best_node: KgNode | None = None
    best_similarity = 0.0
    for candidate in candidates:
        if not candidate.label_embedding:
            continue
        similarity = embeddings.cosine_similarity(query_embedding, candidate.label_embedding)
        if similarity > best_similarity:
            best_similarity = similarity
            best_node = candidate

    if best_node is None or best_similarity < settings.entity_review_threshold:
        return ResolutionResult(node=None, similarity=best_similarity, is_possible_duplicate=False)

    is_possible_duplicate = best_similarity < settings.entity_match_threshold
    return ResolutionResult(
        node=best_node,
        similarity=best_similarity,
        is_possible_duplicate=is_possible_duplicate,
    )
