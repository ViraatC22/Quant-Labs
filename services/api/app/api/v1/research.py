"""Grounded research Q&A, semantic search, claims, and conflicts (Lattice L3/L4)."""

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import Claim, ClaimConflict, ClaimEvidence, ResearchConversation
from app.schemas.research import (
    CitationRead,
    ClaimConflictRead,
    ClaimRead,
    ClaimTimelinePoint,
    ConflictResolveRequest,
    ConversationRead,
    ResearchAnswerRead,
    ResearchAskRequest,
    SearchResultRead,
)
from app.services.research import pipeline, retrieval

router = APIRouter()


@router.post("/ask", response_model=ResearchAnswerRead)
def ask(
    payload: ResearchAskRequest,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ResearchAnswerRead:
    answer = pipeline.answer_question(db, user_id=user_id, question=payload.question)
    db.add(
        ResearchConversation(
            user_id=user_id,
            question=answer.question,
            route=answer.route,
            answer_markdown=answer.answer_markdown,
            trust_score=Decimal(str(answer.trust_score)),
            payload={
                "citations": answer.citations,
                "special_elements": answer.special_elements,
            },
        )
    )
    db.commit()
    return ResearchAnswerRead(
        question=answer.question,
        route=answer.route,
        answer_markdown=answer.answer_markdown,
        trust_score=answer.trust_score,
        citations=[CitationRead(**c) for c in answer.citations],
        special_elements=answer.special_elements,
        retrieved=answer.retrieved,
    )


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ResearchConversation]:
    return list(
        db.scalars(
            select(ResearchConversation)
            .where(ResearchConversation.user_id == user_id)
            .order_by(ResearchConversation.created_at.desc())
            .limit(limit)
        ).all()
    )


@router.get("/search", response_model=list[SearchResultRead])
def search(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    q: Annotated[str, Query(min_length=1, max_length=2000)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[SearchResultRead]:
    results = retrieval.search_chunks(db, user_id=user_id, query=q, limit=limit)
    return [
        SearchResultRead(
            chunk_id=r.chunk_id,
            source_id=r.source_id,
            source_title=r.source_title,
            text=r.text,
            score=r.score,
        )
        for r in results
    ]


@router.get("/claims", response_model=list[ClaimRead])
def list_claims(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    subject_node_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[Claim]:
    query = select(Claim).where(Claim.user_id == user_id)
    if subject_node_id is not None:
        query = query.where(Claim.subject_node_id == subject_node_id)
    return list(db.scalars(query.order_by(Claim.created_at.desc()).limit(limit)).all())


@router.get("/claims/{claim_id}/timeline", response_model=list[ClaimTimelinePoint])
def claim_timeline(
    claim_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[ClaimTimelinePoint]:
    claim = db.get(Claim, claim_id)
    if claim is None or claim.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    evidence = db.scalars(
        select(ClaimEvidence)
        .where(ClaimEvidence.claim_id == claim_id)
        .order_by(ClaimEvidence.asserted_at.asc())
    ).all()
    return [
        ClaimTimelinePoint(
            asserted_at=row.asserted_at,
            stance=row.stance,
            source_document_id=row.source_document_id,
            quote=row.quote,
        )
        for row in evidence
    ]


@router.get("/conflicts", response_model=list[ClaimConflictRead])
def list_conflicts(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    status_filter: Annotated[str, Query(alias="status")] = "open",
) -> list[ClaimConflictRead]:
    conflicts = db.scalars(
        select(ClaimConflict)
        .where(ClaimConflict.user_id == user_id, ClaimConflict.status == status_filter)
        .order_by(ClaimConflict.detected_at.desc())
    ).all()
    out: list[ClaimConflictRead] = []
    for conflict in conflicts:
        claim_a = db.get(Claim, conflict.claim_a_id)
        claim_b = db.get(Claim, conflict.claim_b_id)
        if claim_a is None or claim_b is None:
            continue
        out.append(
            ClaimConflictRead(
                id=conflict.id,
                status=conflict.status,
                detected_at=conflict.detected_at,
                claim_a=ClaimRead.model_validate(claim_a),
                claim_b=ClaimRead.model_validate(claim_b),
            )
        )
    return out


@router.patch("/conflicts/{conflict_id}", response_model=ClaimConflictRead)
def resolve_conflict(
    conflict_id: UUID,
    payload: ConflictResolveRequest,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> ClaimConflictRead:
    conflict = db.get(ClaimConflict, conflict_id)
    if conflict is None or conflict.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conflict not found.")
    conflict.status = payload.status
    conflict.resolution_note = payload.resolution_note
    db.commit()
    db.refresh(conflict)
    claim_a = db.get(Claim, conflict.claim_a_id)
    claim_b = db.get(Claim, conflict.claim_b_id)
    return ClaimConflictRead(
        id=conflict.id,
        status=conflict.status,
        detected_at=conflict.detected_at,
        claim_a=ClaimRead.model_validate(claim_a),
        claim_b=ClaimRead.model_validate(claim_b),
    )
