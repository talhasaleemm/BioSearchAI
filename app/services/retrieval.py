"""Vector retrieval service for semantic search over pgvector embeddings."""

from __future__ import annotations

from typing import List, Optional

import numpy as np
from sqlalchemy import bindparam, func, literal_column, select
from sqlalchemy.orm import Session
from sentence_transformers import CrossEncoder, SentenceTransformer

from app.models.chunk import Chunk
from app.models.document import Document
from app.services.faiss_index import faiss_manager


class VectorRetriever:
    """Semantic retrieval engine backed by PostgreSQL pgvector."""

    RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: str = "pritamdeka/S-PubMedBert-MS-MARCO") -> None:
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None
        self._reranker: Optional[CrossEncoder] = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def reranker(self) -> CrossEncoder:
        if self._reranker is None:
            self._reranker = CrossEncoder(self.RERANKER_MODEL)
        return self._reranker

    def _encode_query(self, query: str) -> np.ndarray:
        """Encode a query string into a normalized 768-dimensional embedding."""
        embedding = self.model.encode(
            [query],
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return np.array(embedding, dtype=np.float32)[0]

    async def search_similar_chunks(
        self,
        db: Session,
        query: str,
        top_k: int = 5,
    ) -> List[tuple[Chunk, Document, float]]:
        """Return the top-k chunks using FAISS retrieval and cross-encoder reranking."""
        query_vector = self._encode_query(query)
        
        distances, indices = await faiss_manager.search(query_vector, top_k * 5)
        
        if indices.size == 0 or indices[0][0] == -1:
            return []
            
        chunk_ids = [int(idx) for idx in indices[0] if idx != -1]
        if not chunk_ids:
            return []
            
        # Fetch actual chunks from DB
        chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
        chunk_map = {chunk.id: chunk for chunk in chunks}
        
        candidates: List[tuple[Chunk, Document, float]] = []
        for idx in chunk_ids:
            if idx in chunk_map:
                chunk = chunk_map[idx]
                candidates.append((chunk, chunk.document, 1.0)) # mock RRF score for now
                
        if not candidates:
            return []

        pairs = [(query, chunk.text) for chunk, _, _ in candidates]
        rerank_scores = self.reranker.predict(pairs)

        reranked = [
            (chunk, document, float(rerank_score))
            for (chunk, document, _), rerank_score in zip(candidates, rerank_scores)
        ]
        reranked.sort(key=lambda item: item[2], reverse=True)

        return reranked[:top_k]
