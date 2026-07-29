from collections import Counter
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import (
    Claim,
    ClaimConflict,
    KgEdge,
    KgNode,
    MemoryChunk,
    SourceDocument,
)
from app.schemas.graph import (
    GraphEvidenceRead,
    GraphNeighborhoodEdgeRead,
    GraphNeighborhoodNodeRead,
    GraphNeighborhoodRead,
    KgEdgeCreate,
    KgEdgeRead,
    KgNodeCreate,
    KgNodeRead,
)
from app.services.research import retrieval

router = APIRouter()


@router.post("/nodes", response_model=KgNodeRead, status_code=201)
def create_node(
    payload: KgNodeCreate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> KgNode:
    node = KgNode(user_id=user_id, **payload.model_dump())
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


@router.get("/nodes", response_model=list[KgNodeRead])
def list_nodes(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    node_type: Annotated[str | None, Query(max_length=80)] = None,
) -> list[KgNode]:
    query = select(KgNode).where(KgNode.user_id == user_id)
    if node_type is not None:
        query = query.where(KgNode.node_type == node_type)
    query = query.order_by(KgNode.label.asc()).offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return list(db.scalars(query).all())


@router.post("/edges", response_model=KgEdgeRead, status_code=201)
def create_edge(
    payload: KgEdgeCreate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> KgEdge:
    expected_count = len({payload.from_node_id, payload.to_node_id})
    node_count = db.scalar(
        select(func.count())
        .where(
            KgNode.user_id == user_id,
            KgNode.id.in_([payload.from_node_id, payload.to_node_id]),
        )
    )
    if node_count != expected_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Both graph nodes must exist for the current user before creating an edge.",
        )

    edge = KgEdge(user_id=user_id, **payload.model_dump())
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge


@router.get("/edges", response_model=list[KgEdgeRead])
def list_edges(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    node_id: Annotated[UUID | None, Query()] = None,
) -> list[KgEdge]:
    query = select(KgEdge).where(KgEdge.user_id == user_id)
    if node_id is not None:
        query = query.where(
            (KgEdge.from_node_id == node_id) | (KgEdge.to_node_id == node_id)
        )
    query = query.order_by(KgEdge.created_at.desc()).offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return list(db.scalars(query).all())


@router.get("/search", response_model=list[KgNodeRead])
def search_nodes(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    q: Annotated[str, Query(min_length=1, max_length=240)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[KgNode]:
    """Entity search: find the graph nodes that best match a query term."""
    return retrieval.link_entities(db, user_id=user_id, query=q, limit=limit)


@router.get("/neighborhood/{node_id}", response_model=GraphNeighborhoodRead)
def node_neighborhood(
    node_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    depth: Annotated[int, Query(ge=1, le=3)] = 1,
) -> GraphNeighborhoodRead:
    """Lazily expand a k-hop neighborhood around one node for the explorer."""
    root = db.get(KgNode, node_id)
    if root is None or root.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found.")
    graph = retrieval.neighborhood(db, user_id=user_id, node_ids=[node_id], depth=depth)
    conflict_counts = _open_conflict_counts(
        db, user_id=user_id, node_ids={node.id for node in graph.nodes}
    )
    evidence_by_chunk = _edge_evidence(
        db,
        user_id=user_id,
        chunk_ids={
            chunk_id
            for edge in graph.edges
            for chunk_id in (edge.evidence_chunk_ids or [])
        },
    )
    return GraphNeighborhoodRead(
        root_id=node_id,
        depth=depth,
        nodes=[
            GraphNeighborhoodNodeRead(
                id=node.id,
                label=node.label,
                node_type=node.node_type,
                confidence=node.confidence,
                properties=node.properties,
                open_conflict_count=conflict_counts.get(node.id, 0),
            )
            for node in graph.nodes
        ],
        edges=[_neighborhood_edge(edge, evidence_by_chunk) for edge in graph.edges],
    )


def _open_conflict_counts(
    db: Session, *, user_id: UUID, node_ids: set[UUID]
) -> Counter[UUID]:
    if not node_ids:
        return Counter()
    conflicts = db.scalars(
        select(ClaimConflict).where(
            ClaimConflict.user_id == user_id,
            ClaimConflict.status == "open",
        )
    ).all()
    claim_ids = {
        claim_id
        for conflict in conflicts
        for claim_id in (conflict.claim_a_id, conflict.claim_b_id)
    }
    if not claim_ids:
        return Counter()
    claims = db.scalars(
        select(Claim).where(
            Claim.user_id == user_id,
            Claim.id.in_(claim_ids),
            Claim.subject_node_id.in_(node_ids),
        )
    ).all()
    subject_by_claim = {claim.id: claim.subject_node_id for claim in claims}
    counts: Counter[UUID] = Counter()
    for conflict in conflicts:
        subject_ids = {
            subject_by_claim.get(conflict.claim_a_id),
            subject_by_claim.get(conflict.claim_b_id),
        }
        for subject_id in subject_ids:
            if subject_id is not None:
                counts[subject_id] += 1
    return counts


def _edge_evidence(
    db: Session, *, user_id: UUID, chunk_ids: set[UUID]
) -> dict[UUID, GraphEvidenceRead]:
    if not chunk_ids:
        return {}
    chunks = db.scalars(
        select(MemoryChunk).where(
            MemoryChunk.user_id == user_id,
            MemoryChunk.id.in_(chunk_ids),
        )
    ).all()
    document_ids = {
        chunk.source_id for chunk in chunks if chunk.source_type == "source_document"
    }
    titles = (
        {
            document.id: document.title
            for document in db.scalars(
                select(SourceDocument).where(
                    SourceDocument.user_id == user_id,
                    SourceDocument.id.in_(document_ids),
                )
            ).all()
        }
        if document_ids
        else {}
    )
    return {
        chunk.id: GraphEvidenceRead(
            chunk_id=chunk.id,
            source_document_id=(
                chunk.source_id if chunk.source_type == "source_document" else None
            ),
            source_title=str(
                (chunk.chunk_metadata or {}).get("source_title")
                or titles.get(chunk.source_id)
                or chunk.source_type
            ),
            text=chunk.text,
        )
        for chunk in chunks
    }


def _neighborhood_edge(
    edge: KgEdge, evidence_by_chunk: dict[UUID, GraphEvidenceRead]
) -> GraphNeighborhoodEdgeRead:
    evidence = [
        evidence_by_chunk[chunk_id]
        for chunk_id in (edge.evidence_chunk_ids or [])
        if chunk_id in evidence_by_chunk
    ]
    raw_sources = (edge.properties or {}).get("source_titles", [])
    property_sources = raw_sources if isinstance(raw_sources, list) else []
    contributing_sources = sorted(
        {
            str(title).strip()
            for title in [*property_sources, *(item.source_title for item in evidence)]
            if str(title).strip()
        }
    )
    return GraphNeighborhoodEdgeRead(
        id=edge.id,
        edge_type=edge.edge_type,
        from_node_id=edge.from_node_id,
        to_node_id=edge.to_node_id,
        confidence=edge.confidence,
        properties=edge.properties,
        evidence_chunk_ids=list(edge.evidence_chunk_ids or []),
        evidence_count=len(edge.evidence_chunk_ids or []),
        contributing_sources=contributing_sources,
        evidence=evidence,
    )
