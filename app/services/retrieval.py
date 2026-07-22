"""Vector retrieval service for semantic search over pgvector embeddings."""

from __future__ import annotations

from typing import List, Optional

import numpy as np
from sqlalchemy import bindparam, func, literal_column, select
from sqlalchemy.orm import Session
from sentence_transformers import CrossEncoder, SentenceTransformer

from app.models.chunk import Chunk
from app.models.document import Document


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

    def search_similar_chunks(
        self,
        db: Session,
        query: str,
        top_k: int = 5,
    ) -> List[tuple[Chunk, Document, float]]:
        """Return the top-k chunks using hybrid dense+sparse retrieval with RRF
        and cross-encoder reranking.

        Args:
            db: SQLAlchemy database session.
            query: Natural language query string.
            top_k: Maximum number of results to return.

        Returns:
            List of tuples ``(Chunk, Document, reranker_score)`` ordered by
            descending cross-encoder score.
        """
        query_vector = self._encode_query(query)
        query_text = query

        query_text_param = bindparam("query_text")
        ts_query = func.websearch_to_tsquery("english", query_text_param)

        dense_cte = (
            select(
                Chunk.id,
                func.row_number()
                .over(order_by=Chunk.embedding.cosine_distance(query_vector))
                .label("dense_rank"),
            )
            .where(Chunk.embedding.is_not(None))
            .limit(50)
            .cte("dense_cte")
        )

        sparse_cte = (
            select(
                Chunk.id,
                func.row_number()
                .over(order_by=func.ts_rank(Chunk.fts_vector, ts_query).desc())
                .label("sparse_rank"),
            )
            .where(Chunk.fts_vector.op("@@")(ts_query))
            .limit(50)
            .cte("sparse_cte")
        )

        rrf_score = (
            func.coalesce(literal_column("1.0") / (literal_column(60) + dense_cte.c.dense_rank), 0.0)
            + func.coalesce(literal_column("1.0") / (literal_column(60) + sparse_cte.c.sparse_rank), 0.0)
        ).label("rrf_score")

        final_stmt = (
            select(
                Chunk,
                Document,
                rrf_score,
            )
            .outerjoin(dense_cte, Chunk.id == dense_cte.c.id)
            .outerjoin(sparse_cte, Chunk.id == sparse_cte.c.id)
            .join(Document, Chunk.document_id == Document.id)
            .order_by(rrf_score.desc())
            .limit(25)
        )

        candidates: List[tuple[Chunk, Document, float]] = []
        for chunk, document, score in db.execute(final_stmt, {"query_text": query_text}).all():
            candidates.append((chunk, document, float(score)))

        if not candidates:
            return []

        pairs = [(query_text, chunk.text) for chunk, _, _ in candidates]
        rerank_scores = self.reranker.predict(pairs)

        reranked = [
            (chunk, document, float(rerank_score))
            for (chunk, document, _), rerank_score in zip(candidates, rerank_scores)
        ]
        reranked.sort(key=lambda item: item[2], reverse=True)

        return reranked[:top_k]
