"""Vector retrieval service for semantic search over FAISS + PostgreSQL."""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from app.models.chunk import Chunk
from app.models.document import Document
from app.services.faiss_index import faiss_manager
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class VectorRetriever:
    """Semantic retrieval engine backed by FAISS in-memory index + PostgreSQL source of truth.

    Cross-encoder reranking is used when the model is available locally.  If the
    model file cannot be loaded (offline environment, model not yet downloaded),
    reranking is skipped and results are returned ordered by raw FAISS inner-product
    score (cosine similarity on normalized vectors).
    """

    # Bare HF model ID kept for reference / future local download.
    # Set RERANKER_MODEL_PATH in settings to point at a local directory instead.
    RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or get_settings().EMBEDDING_MODEL_PATH
        self._model: Optional[SentenceTransformer] = None
        # _reranker is None until first use; stays None permanently if load fails.
        self._reranker_loaded: bool = False
        self._reranker = None  # type: ignore[assignment]

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _load_reranker(self) -> None:
        """Attempt to load the cross-encoder reranker once.  Sets to None on failure."""
        if self._reranker_loaded:
            return
        self._reranker_loaded = True
        reranker_path = getattr(get_settings(), "RERANKER_MODEL_PATH", None)
        model_id = reranker_path or self.RERANKER_MODEL
        try:
            from sentence_transformers import CrossEncoder  # local import to avoid startup cost
            self._reranker = CrossEncoder(model_id)
            logger.info("Cross-encoder reranker loaded from: %s", model_id)
        except Exception as exc:
            logger.warning(
                "Cross-encoder reranker could not be loaded (%s: %s). "
                "Retrieval will proceed without reranking — results are ordered by "
                "FAISS cosine similarity score.",
                type(exc).__name__,
                exc,
            )
            self._reranker = None

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
        """Return the top-k chunks using FAISS retrieval and (optional) cross-encoder reranking."""
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

        # Build candidate list preserving FAISS rank order and carrying the raw score.
        dist_map = {int(indices[0][i]): float(distances[0][i]) for i in range(len(indices[0])) if indices[0][i] != -1}
        candidates: List[tuple[Chunk, Document, float]] = []
        for idx in chunk_ids:
            if idx in chunk_map:
                chunk = chunk_map[idx]
                candidates.append((chunk, chunk.document, dist_map.get(idx, 0.0)))

        if not candidates:
            return []

        # Attempt cross-encoder reranking; fall back gracefully if unavailable.
        self._load_reranker()
        if self._reranker is not None:
            pairs = [(query, chunk.text) for chunk, _, _ in candidates]
            rerank_scores = self._reranker.predict(pairs)
            candidates = [
                (chunk, document, float(rerank_score))
                for (chunk, document, _), rerank_score in zip(candidates, rerank_scores)
            ]

        candidates.sort(key=lambda item: item[2], reverse=True)
        return candidates[:top_k]
