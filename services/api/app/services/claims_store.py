"""Persist extracted claims and detect conflicts (Lattice L4).

Upserts are replay-safe: re-importing the same source lands on the same
``(subject, predicate, object, polarity)`` tuple and adds no duplicate claim,
while a second source agreeing adds an evidence row (reinforcement) and a
second source disagreeing creates the opposing-polarity claim which conflict
detection then pairs.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import Claim, ClaimConflict, ClaimEvidence, KgNode
from app.services import embeddings
from app.services.claim_extraction import ExtractedClaim


def persist_claims(
    db: Session,
    *,
    user_id: UUID,
    subject_node: KgNode,
    document_id: UUID,
    extracted: list[ExtractedClaim],
    chunk_ids: list[UUID],
) -> list[Claim]:
    """Upsert claims for one document and return the persisted rows."""
    evidence_chunk = chunk_ids[0] if chunk_ids else None
    persisted: list[Claim] = []
    for item in extracted:
        claim = _upsert_claim(
            db,
            user_id=user_id,
            subject_node_id=subject_node.id,
            item=item,
        )
        _add_evidence(
            db,
            claim=claim,
            document_id=document_id,
            chunk_id=evidence_chunk,
            item=item,
        )
        persisted.append(claim)
    return persisted


def _upsert_claim(
    db: Session,
    *,
    user_id: UUID,
    subject_node_id: UUID,
    item: ExtractedClaim,
) -> Claim:
    existing = db.scalar(
        select(Claim).where(
            Claim.user_id == user_id,
            Claim.subject_node_id == subject_node_id,
            Claim.predicate == item.predicate,
            Claim.object_literal == item.object_literal,
            Claim.polarity == item.polarity,
        )
    )
    if existing:
        existing.confidence = _max_confidence(existing.confidence, item.confidence)
        return existing

    claim = Claim(
        user_id=user_id,
        subject_node_id=subject_node_id,
        predicate=item.predicate,
        object_literal=item.object_literal,
        polarity=item.polarity,
        statement_text=item.statement_text,
        embedding=embeddings.embed_text(item.statement_text),
        confidence=item.confidence,
    )
    db.add(claim)
    db.flush()
    return claim


def _add_evidence(
    db: Session,
    *,
    claim: Claim,
    document_id: UUID,
    chunk_id: UUID | None,
    item: ExtractedClaim,
) -> None:
    already = db.scalar(
        select(ClaimEvidence).where(
            ClaimEvidence.claim_id == claim.id,
            ClaimEvidence.source_document_id == document_id,
        )
    )
    if already:
        return
    stance = "contradicts" if item.polarity == "refutes" else "supports"
    db.add(
        ClaimEvidence(
            claim_id=claim.id,
            source_document_id=document_id,
            chunk_id=chunk_id,
            stance=stance,
            quote=item.quote,
        )
    )
    db.flush()


def detect_conflicts_for_subject(db: Session, *, user_id: UUID, subject_node_id: UUID) -> int:
    """Open conflicts among the claims about one subject. Returns new count.

    Two claims conflict when they share subject+predicate+object but oppose in
    polarity, or when their statement embeddings are highly similar yet oppose.
    """
    claims = db.scalars(
        select(Claim).where(
            Claim.user_id == user_id,
            Claim.subject_node_id == subject_node_id,
        )
    ).all()
    new_conflicts = 0
    for i, claim_a in enumerate(claims):
        for claim_b in claims[i + 1 :]:
            if not _opposes(claim_a, claim_b):
                continue
            if _conflict_exists(db, user_id, claim_a.id, claim_b.id):
                continue
            db.add(
                ClaimConflict(
                    user_id=user_id,
                    claim_a_id=claim_a.id,
                    claim_b_id=claim_b.id,
                )
            )
            new_conflicts += 1
    if new_conflicts:
        db.flush()
    return new_conflicts


def _opposes(a: Claim, b: Claim) -> bool:
    if a.polarity == b.polarity:
        return False
    if "neutral" in (a.polarity, b.polarity):
        return False
    same_triple = a.predicate == b.predicate and a.object_literal == b.object_literal
    if same_triple:
        return True
    similarity = embeddings.cosine_similarity(a.embedding, b.embedding)
    return similarity >= settings.conflict_sim_threshold


def _conflict_exists(db: Session, user_id: UUID, a_id: UUID, b_id: UUID) -> bool:
    return (
        db.scalar(
            select(ClaimConflict.id).where(
                ClaimConflict.user_id == user_id,
                or_(
                    (ClaimConflict.claim_a_id == a_id) & (ClaimConflict.claim_b_id == b_id),
                    (ClaimConflict.claim_a_id == b_id) & (ClaimConflict.claim_b_id == a_id),
                ),
            )
        )
        is not None
    )


def _max_confidence(current: Decimal | None, incoming: Decimal | None) -> Decimal | None:
    values = [value for value in (current, incoming) if value is not None]
    return max(values) if values else None
