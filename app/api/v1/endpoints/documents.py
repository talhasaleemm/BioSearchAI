"""API v1 document ingestion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.document import Document
from app.models.user import User
from app.models.search_session import SearchSession
from app.tasks.worker import process_document_task
from app.services.pubmed import pubmed_service

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


class PubMedSearchRequest(BaseModel):
    query: str
    max_results: int = 10


class PubMedSearchResultItem(BaseModel):
    pmid: str
    title: str
    abstract: str
    year: str


class PubMedSearchResponse(BaseModel):
    results: List[PubMedSearchResultItem]


class PubMedIngestRequest(BaseModel):
    pmid: str
    session_id: int


@router.post("/ingest", response_model=DocumentIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(
    payload: DocumentIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DocumentIngestResponse:
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


@router.post("/pubmed-search", response_model=PubMedSearchResponse)
async def pubmed_search(
    payload: PubMedSearchRequest,
    current_user: User = Depends(get_current_user)
) -> PubMedSearchResponse:
    """Search PubMed and return abstracts for the top results."""
    try:
        pmids = await pubmed_service.search_pubmed(payload.query, payload.max_results)
        abstracts = await pubmed_service.fetch_pubmed_abstracts(pmids)
        return PubMedSearchResponse(results=[PubMedSearchResultItem(**item) for item in abstracts])
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/pubmed-ingest", response_model=DocumentIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def pubmed_ingest(
    payload: PubMedIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DocumentIngestResponse:
    """Ingest a specific PubMed abstract by PMID into the session."""
    session = db.get(SearchSession, payload.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SearchSession {payload.session_id} not found.",
        )

    try:
        abstracts = await pubmed_service.fetch_pubmed_abstracts([payload.pmid])
        if not abstracts:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"PMID {payload.pmid} not found on PubMed.")
            
        abstract_data = abstracts[0]
        if not abstract_data.get("abstract"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No abstract available for PMID {payload.pmid}")

        document = Document(
            session_id=payload.session_id,
            title=abstract_data.get("title", "Untitled PubMed Article"),
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{payload.pmid}/",
            source_type="pubmed",
            content=abstract_data.get("abstract"),
            status="pending",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        process_document_task.delay(document.id)

        return DocumentIngestResponse(
            id=document.id,
            status="pending",
            message="PubMed document queued for processing.",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/pdf-ingest", response_model=DocumentIngestResponse, status_code=status.HTTP_202_ACCEPTED)
async def pdf_ingest(
    file: UploadFile = File(...),
    session_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DocumentIngestResponse:
    """Ingest a PDF document, extract text in-memory, and trigger background processing."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a PDF")
        
    session = db.get(SearchSession, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SearchSession {session_id} not found.",
        )
        
    try:
        content = await file.read()
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        text_parts = []
        for page in doc:
            text = page.get_text()
            if text:
                text_parts.append(text)
            
        full_text = "\n\n".join(text_parts).strip()
        if not full_text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No extractable text found in PDF (might be a scanned image).")
            
        document = Document(
            session_id=session_id,
            title=file.filename,
            source_url=None,
            source_type="pdf",
            content=full_text,
            status="pending",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        
        process_document_task.delay(document.id)
        
        return DocumentIngestResponse(
            id=document.id,
            status="pending",
            message="PDF document queued for processing.",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
