"""RAG engine combining retrieval with grounded LLM generation."""

from __future__ import annotations

import json
import re
from typing import AsyncIterator, List, Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.rag import RAGResponse
from app.schemas.search import ChunkResult, DocumentMetadata
from app.services.retrieval import VectorRetriever

settings = get_settings()

_SYSTEM_PROMPT = (
    "You are a strict biomedical research assistant. "
    "Answer the prompt strictly using the provided scientific context. "
    "Cite source PMIDs/DOIs in brackets. "
    "If context is insufficient, state that clearly. "
    "Do not hallucinate outside the provided context."
)


def _extract_pmid(source_url: Optional[str]) -> Optional[str]:
    if not source_url or "pubmed.ncbi.nlm.nih.gov" not in source_url:
        return None
    match = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", source_url)
    if match:
        return match.group(1)
    return None


def _build_context(results: List[ChunkResult]) -> str:
    """Format retrieved chunks into a cited context string for the LLM."""
    parts: List[str] = []
    for idx, result in enumerate(results, start=1):
        source_id = None
        if result.document and result.document.source_id:
            source_id = _extract_pmid(result.document.source_id) or result.document.source_id

        title = result.document.title if result.document else "Unknown"
        parts.append(f"[Source {idx} | PMID: {source_id or 'N/A'} | Title: {title}]\n{result.text}")
    return "\n\n".join(parts)


class RAGEngine:
    """Retrieval-Augmented Generation engine with citation guardrails."""

    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.retriever = VectorRetriever()
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE,
            )
        return self._client

    def generate_answer(self, db: Session, query: str, top_k: int = 5, temperature: float = 0.2) -> RAGResponse:
        """Run retrieval and generate a grounded answer.

        Args:
            db: SQLAlchemy database session.
            query: Natural language query.
            top_k: Number of chunks to retrieve.
            temperature: LLM temperature for generation.

        Returns:
            ``RAGResponse`` containing the answer and source list.
        """
        results = self.retriever.search_similar_chunks(db=db, query=query, top_k=top_k)

        sources: List[ChunkResult] = []
        for chunk, document, similarity in results:
            sources.append(
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

        context = _build_context(sources)
        user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

        completion = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=temperature,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        answer = completion.choices[0].message.content or ""

        return RAGResponse(query=query, answer=answer, sources=sources)

    async def stream_answer(self, db: Session, query: str, top_k: int = 5, temperature: float = 0.2) -> AsyncIterator[str]:
        """Stream a grounded RAG answer as SSE events.

        Args:
            db: SQLAlchemy database session.
            query: Natural language query.
            top_k: Number of chunks to retrieve.
            temperature: LLM temperature for generation.

        Yields:
            SSE-formatted strings. The first payload contains sources metadata,
            followed by streamed completion tokens.
        """
        results = self.retriever.search_similar_chunks(db=db, query=query, top_k=top_k)

        sources: List[ChunkResult] = []
        for chunk, document, similarity in results:
            sources.append(
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

        sources_payload = json.dumps({"type": "sources", "sources": [s.model_dump() for s in sources]})
        yield f"data: {sources_payload}\n\n"

        context = _build_context(sources)
        user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

        stream = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=temperature,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                yield f"data: {token}\n\n"
