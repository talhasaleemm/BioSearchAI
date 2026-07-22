"""Pydantic v2 schemas for RAG pipeline requests and responses."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from app.schemas.search import ChunkResult


class RAGRequest(BaseModel):
    """Request payload for RAG answer generation."""

    query: str
    top_k: int = 5
    temperature: float = 0.2


class RAGResponse(BaseModel):
    """Validated RAG response payload with grounded answer and sources."""

    query: str
    answer: str
    sources: List[ChunkResult]
