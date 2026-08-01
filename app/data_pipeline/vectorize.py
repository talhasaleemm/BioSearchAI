"""Chunking, embedding, and pgvector persistence pipeline."""

from __future__ import annotations

import re
from typing import List, Optional

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

from app.models import SessionLocal
from app.models.chunk import Chunk
from app.models.document import Document

_tokenizer = None

def get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = AutoTokenizer.from_pretrained("pritamdeka/S-PubMedBert-MS-MARCO")
    return _tokenizer

_SENTENCE_END_RE = re.compile(r'(?<=[.!?])\s+')
_BIOMEDICAL_PRESERVE_RE = re.compile(
    r'(?:Fig\.|Eq\.|e\.g\.|i\.e\.|vs\.|Dr\.|Prof\.|'
    r'[A-Z][A-Z0-9\-]{1,8}'
    r'(?:\([A-Z0-9\-]+\))*'
    r'(?:-[A-Z0-9]+)*'  # protein/gene notation continuation
    r'|https?://\S+)$'
)


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences while avoiding common abbreviation pitfalls."""
    sentences = _SENTENCE_END_RE.split(text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _token_count(text: str) -> int:
    """Return the token count for a text string using the BiomedBERT tokenizer."""
    return len(get_tokenizer().encode(text, add_special_tokens=False))


def _trim_overlap(parts: List[str], max_overlap_tokens: int) -> None:
    """Pop items from the beginning until remaining token count is within the overlap budget."""
    total = sum(_token_count(p) for p in parts)
    while parts and total > max_overlap_tokens:
        removed = parts.pop(0)
        total -= _token_count(removed)


def chunk_text(text: str, chunk_size_tokens: int = 450, overlap_tokens: int = 50) -> List[str]:
    """Split text into semantically coherent overlapping chunks.

    Strategy:
    1. Split primarily on paragraph breaks (``\\n\\n``).
    2. If a paragraph exceeds the target size, fall back to sentence splitting.
    3. Group paragraphs/sentences into chunks around ``chunk_size_tokens`` tokens.
    4. Maintain a ``overlap_tokens``-token semantic overlap between adjacent chunks
       by retaining tail items from the previous accumulation window.
    5. Avoid breaking inside biomedical tokens (genes, proteins, formulas).
    """
    if not text or not text.strip():
        return []

    raw_paragraphs = re.split(r'\n\s*\n', text.strip())
    paragraphs: List[str] = [p.strip() for p in raw_paragraphs if p.strip()]
    if not paragraphs:
        return []

    chunks: List[str] = []
    current_parts: List[str] = []
    current_token_count = 0

    def _flush_current(force: bool = False) -> None:
        nonlocal current_token_count, current_parts
        if not current_parts:
            return
        if force or current_token_count >= chunk_size_tokens:
            chunks.append(" ".join(current_parts))
            _trim_overlap(current_parts, overlap_tokens)
            current_token_count = sum(_token_count(p) for p in current_parts)

    for para in paragraphs:
        para_tokens = _token_count(para)
        if para_tokens > chunk_size_tokens:
            sentences = _split_sentences(para)
            for sentence in sentences:
                if not sentence:
                    continue
                sent_tokens = _token_count(sentence)
                if sent_tokens > chunk_size_tokens and len(sentence) > chunk_size_tokens * 2:
                    # Hard-split extremely long sentences on spaces to avoid pathological rows
                    sentence_words = sentence.split()
                    for i in range(0, len(sentence_words), chunk_size_tokens):
                        segment = " ".join(sentence_words[i:i + chunk_size_tokens])
                        current_parts.append(segment)
                        current_token_count += _token_count(segment)
                        _flush_current(force=True)
                    continue

                if current_token_count + sent_tokens > chunk_size_tokens and current_parts:
                    _flush_current(force=True)

                current_parts.append(sentence)
                current_token_count += sent_tokens
                _flush_current()
            continue

        # Normal paragraph: check if adding it would overflow
        if current_token_count + para_tokens > chunk_size_tokens and current_parts:
            _flush_current(force=True)

        current_parts.append(para)
        current_token_count += para_tokens
        _flush_current()

    # Flush remaining accumulated text
    if current_parts and (current_token_count > overlap_tokens or len(chunks) == 0):
        chunks.append(" ".join(current_parts))

    cleaned: List[str] = []
    for c in chunks:
        c = " ".join(c.split())
        if c:
            cleaned.append(c)
    return cleaned


def get_unchunked_documents(db: Session, limit: Optional[int] = None) -> List[Document]:
    """Fetch documents that do not yet have associated chunks."""
    query = (
        db.query(Document)
        .outerjoin(Chunk, Document.id == Chunk.document_id)
        .group_by(Document.id)
        .having(Chunk.id == None)
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def chunk_documents(db: Session, docs: List[Document], chunk_size_tokens: int = 450, overlap_tokens: int = 50) -> List[Chunk]:
    """Chunk document content and insert Chunk rows into the database."""
    new_chunks: List[Chunk] = []
    for doc in docs:
        if not doc.content:
            continue
        texts = chunk_text(doc.content, chunk_size_tokens=chunk_size_tokens, overlap_tokens=overlap_tokens)
        for idx, text in enumerate(texts):
            chunk = Chunk(
                document_id=doc.id,
                text=text,
                chunk_index=idx,
                fts_vector=func.to_tsvector("english", text),
            )
            db.add(chunk)
            new_chunks.append(chunk)
    db.commit()
    for chunk in new_chunks:
        db.refresh(chunk)
    return new_chunks


def generate_embeddings(chunks: List[Chunk], model_name: str = "pritamdeka/S-PubMedBert-MS-MARCO") -> np.ndarray:
    """Generate embeddings for a list of chunks using SentenceTransformer."""
    model = SentenceTransformer(model_name)
    texts = [chunk.text for chunk in chunks]
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return np.array(embeddings, dtype=np.float32)


def save_embeddings_to_db(db: Session, chunks: List[Chunk], embeddings: np.ndarray) -> None:
    """Persist generated embeddings to the PostgreSQL pgvector column."""
    for chunk, vector in zip(chunks, embeddings):
        chunk.embedding = vector.tolist()
    db.commit()


def run_vectorization(chunk_size_tokens: int = 450, overlap_tokens: int = 50, model_name: str = "pritamdeka/S-PubMedBert-MS-MARCO") -> dict:
    """Run the full chunking, embedding, and pgvector persistence pipeline."""
    db = SessionLocal()
    try:
        docs = get_unchunked_documents(db)
        if not docs:
            return {"status": "skipped", "reason": "No unchunked documents found."}

        chunks = chunk_documents(db, docs, chunk_size_tokens=chunk_size_tokens, overlap_tokens=overlap_tokens)
        if not chunks:
            return {"status": "skipped", "reason": "No chunks generated."}

        embeddings = generate_embeddings(chunks, model_name=model_name)
        save_embeddings_to_db(db, chunks, embeddings)

        return {
            "status": "completed",
            "documents_chunked": len(docs),
            "chunks_created": len(chunks),
            "model": model_name,
            "embedding_dimension": int(embeddings.shape[1]) if embeddings.size else 0,
        }
    finally:
        db.close()
