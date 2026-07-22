"""Pydantic v2 schemas for search API responses."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    """Document-level metadata returned with each search result."""

    id: int
    title: str
    source_id: Optional[str] = None
    doi: Optional[str] = None


class ChunkResult(BaseModel):
    """Single search result chunk with similarity score, metadata, and parent document."""

    id: int
    text: str
    chunk_index: int
    similarity_score: float
    metadata: Optional[dict] = None
    document: Optional[DocumentMetadata] = None


class SearchResponse(BaseModel):
    """Validated search response payload."""

    query: str
    results_count: int
    results: List[ChunkResult]
