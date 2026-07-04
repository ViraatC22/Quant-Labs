from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import TaxonomyItem
from app.schemas.graph import TaxonomyItemCreate, TaxonomyItemRead

router = APIRouter()


@router.post("/items", response_model=TaxonomyItemRead, status_code=201)
def create_taxonomy_item(
    payload: TaxonomyItemCreate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> TaxonomyItem:
    item = TaxonomyItem(user_id=user_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/items", response_model=list[TaxonomyItemRead])
def list_taxonomy_items(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    taxonomy_type: Annotated[str | None, Query(max_length=80)] = None,
) -> list[TaxonomyItem]:
    query = select(TaxonomyItem).where(TaxonomyItem.user_id == user_id)
    if taxonomy_type:
        query = query.where(TaxonomyItem.taxonomy_type == taxonomy_type)

    return list(
        db.scalars(query.order_by(TaxonomyItem.taxonomy_type.asc(), TaxonomyItem.label.asc())).all()
    )
