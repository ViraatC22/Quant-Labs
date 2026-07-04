from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import JournalEntry, SourceDocument
from app.schemas.vault import (
    JournalEntryCreate,
    JournalEntryRead,
    SourceDocumentCreate,
    SourceDocumentRead,
)

router = APIRouter()


def _document_read(document: SourceDocument) -> SourceDocumentRead:
    return SourceDocumentRead(
        id=document.id,
        title=document.title,
        document_type=document.document_type,
        uri=document.uri,
        content_text=document.content_text,
        metadata=document.source_metadata,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _journal_read(entry: JournalEntry) -> JournalEntryRead:
    return JournalEntryRead(
        id=entry.id,
        entry_date=entry.entry_date,
        title=entry.title,
        body=entry.body,
        emotional_state=entry.emotional_state,
        tags=entry.tags,
        metadata=entry.journal_metadata,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.post("/documents", response_model=SourceDocumentRead, status_code=201)
def create_document(
    payload: SourceDocumentCreate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SourceDocumentRead:
    document = SourceDocument(
        user_id=user_id,
        title=payload.title,
        document_type=payload.document_type,
        uri=payload.uri,
        content_text=payload.content_text,
        source_metadata=payload.metadata,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return _document_read(document)


@router.get("/documents", response_model=list[SourceDocumentRead])
def list_documents(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[SourceDocumentRead]:
    documents = db.scalars(
        select(SourceDocument)
        .where(SourceDocument.user_id == user_id)
        .order_by(SourceDocument.created_at.desc())
    ).all()
    return [_document_read(document) for document in documents]


@router.post("/journal-entries", response_model=JournalEntryRead, status_code=201)
def create_journal_entry(
    payload: JournalEntryCreate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> JournalEntryRead:
    entry = JournalEntry(
        user_id=user_id,
        entry_date=payload.entry_date,
        title=payload.title,
        body=payload.body,
        emotional_state=payload.emotional_state,
        tags=payload.tags,
        journal_metadata=payload.metadata,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _journal_read(entry)


@router.get("/journal-entries", response_model=list[JournalEntryRead])
def list_journal_entries(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[JournalEntryRead]:
    entries = db.scalars(
        select(JournalEntry)
        .where(JournalEntry.user_id == user_id)
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
    ).all()
    return [_journal_read(entry) for entry in entries]
