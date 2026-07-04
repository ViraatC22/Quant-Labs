from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import KgEdge, KgNode
from app.schemas.graph import KgEdgeCreate, KgEdgeRead, KgNodeCreate, KgNodeRead

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
