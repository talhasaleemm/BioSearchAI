"""API v1 RAG endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.rag import RAGRequest, RAGResponse
from app.schemas.search import ChunkResult, DocumentMetadata
from app.services.rag import RAGEngine

router = APIRouter(prefix="/api/v1", tags=["rag"])
_rag_engine = None


def get_rag_engine():
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine


@router.post("/rag/generate", response_model=RAGResponse)
async def generate_rag_answer(payload: RAGRequest, db: Session = Depends(get_db)) -> RAGResponse:
    """Generate a grounded answer using RAG with citation guardrails.

    Args:
        payload: RAG request containing query and retrieval parameters.
        db: Injected database session.

    Returns:
        Validated ``RAGResponse`` with generated answer and sources.
    """
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query must not be empty.",
        )

    try:
        response = await get_rag_engine().generate_answer(
            db=db,
            query=payload.query,
            top_k=payload.top_k,
            temperature=payload.temperature,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG generation failed: {exc}",
        ) from exc

    return response


@router.post("/rag/stream")
async def stream_rag_answer(payload: RAGRequest, db: Session = Depends(get_db)):
    """Stream a grounded RAG answer using Server-Sent Events.

    Args:
        payload: RAG request containing query and retrieval parameters.
        db: Injected database session.

    Returns:
        ``StreamingResponse`` emitting SSE events with sources metadata
        and generated tokens.
    """
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query must not be empty.",
        )

    async def event_generator():
        async for chunk in get_rag_engine().stream_answer(
            db=db,
            query=payload.query,
            top_k=payload.top_k,
            temperature=payload.temperature,
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
