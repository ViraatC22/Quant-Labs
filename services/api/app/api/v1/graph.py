from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import KgEdge, KgNode
from app.schemas.graph import KgEdgeCreate, KgEdgeRead, KgNodeCreate, KgNodeRead
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
) -> list[KgNode]:
    return list(
        db.scalars(
            select(KgNode).where(KgNode.user_id == user_id).order_by(KgNode.label.asc())
        ).all()
    )


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
) -> list[KgEdge]:
    return list(
        db.scalars(
            select(KgEdge).where(KgEdge.user_id == user_id).order_by(KgEdge.created_at.desc())
        ).all()
    )


@router.get("/search", response_model=list[KgNodeRead])
def search_nodes(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    q: Annotated[str, Query(min_length=1, max_length=240)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[KgNode]:
    """Entity search: find the graph nodes that best match a query term."""
    return retrieval.link_entities(db, user_id=user_id, query=q, limit=limit)


@router.get("/neighborhood/{node_id}")
def node_neighborhood(
    node_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    depth: Annotated[int, Query(ge=1, le=3)] = 1,
) -> dict:
    """Lazily expand a k-hop neighborhood around one node for the explorer."""
    root = db.get(KgNode, node_id)
    if root is None or root.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found.")
    graph = retrieval.neighborhood(db, user_id=user_id, node_ids=[node_id], depth=depth)
    return {
        "root_id": str(node_id),
        "depth": depth,
        "nodes": [
            {
                "id": str(node.id),
                "label": node.label,
                "node_type": node.node_type,
                "confidence": float(node.confidence) if node.confidence is not None else None,
                "properties": node.properties,
            }
            for node in graph.nodes
        ],
        "edges": [
            {
                "id": str(edge.id),
                "edge_type": edge.edge_type,
                "from_node_id": str(edge.from_node_id),
                "to_node_id": str(edge.to_node_id),
                "confidence": float(edge.confidence) if edge.confidence is not None else None,
                "evidence_chunk_ids": [str(cid) for cid in (edge.evidence_chunk_ids or [])],
            }
            for edge in graph.edges
        ],
    }
