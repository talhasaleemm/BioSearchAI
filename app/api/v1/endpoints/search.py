"""API v1 search endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.search import ChunkResult, DocumentMetadata, SearchResponse
from app.services.retrieval import VectorRetriever

router = APIRouter(prefix="/api/v1", tags=["search"])
_retriever = None

def get_retriever() -> VectorRetriever:
    global _retriever
    if _retriever is None:
        _retriever = VectorRetriever()
    return _retriever


class SearchQuery(BaseModel):
    """Request payload for semantic search."""

    query: str
    top_k: int = 5


@router.post("/search", response_model=SearchResponse)
async def search_chunks(payload: SearchQuery, db: Session = Depends(get_db)) -> SearchResponse:
    """Semantic search across chunk embeddings using pgvector.

    Args:
        payload: Search query and retrieval parameters.
        db: Injected database session.

    Returns:
        Validated ``SearchResponse`` with ranked chunk results.
    """
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query must not be empty.",
        )

    try:
        retriever = get_retriever()
        results = await retriever.search_similar_chunks(
            db=db,
            query=payload.query,
            top_k=payload.top_k,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retrieval failed: {exc}",
        ) from exc

    chunk_results: List[ChunkResult] = []
    for chunk, document, similarity in results:
        chunk_results.append(
            ChunkResult(
                id=chunk.id,
                text=chunk.text,
                chunk_index=chunk.chunk_index,
                similarity_score=round(similarity, 6),
                metadata=chunk.chunk_metadata,
                document=DocumentMetadata(
                    id=document.id,
                    title=document.title,
                    source_id=document.source_url,
                    doi=None,
                ),
            )
        )

    # Extract entities from the search query
    from app.services.ner import ner_service
    extracted_entities = ner_service.extract_entities(payload.query)

    return SearchResponse(
        query=payload.query,
        extracted_entities=extracted_entities,
        results_count=len(chunk_results),
        results=chunk_results,
    )
