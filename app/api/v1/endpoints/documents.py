"""API v1 document ingestion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.document import Document
from app.models.search_session import SearchSession
from app.tasks.worker import process_document_task

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


class DocumentIngestRequest(BaseModel):
    """Request payload for document ingestion."""

    title: str
    source_type: str
    source_url: str | None = None
    content: str | None = None
    session_id: int


class DocumentIngestResponse(BaseModel):
    """Response payload for document ingestion."""

    id: int
    status: str
    message: str


@router.post("/ingest", response_model=DocumentIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(payload: DocumentIngestRequest, db: Session = Depends(get_db)) -> DocumentIngestResponse:
    """Ingest a new document and trigger async background processing.

    Args:
        payload: Document metadata and optional content.
        db: Injected database session.

    Returns:
        202 Accepted with the created document ID and queued status.
    """
    session = db.get(SearchSession, payload.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SearchSession {payload.session_id} not found.",
        )

    document = Document(
        session_id=payload.session_id,
        title=payload.title,
        source_url=payload.source_url,
        source_type=payload.source_type,
        content=payload.content,
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    process_document_task.delay(document.id)

    return DocumentIngestResponse(
        id=document.id,
        status="pending",
        message="Document queued for processing.",
    )
