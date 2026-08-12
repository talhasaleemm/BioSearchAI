"""Background worker tasks for BioSearchAI."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.data_pipeline.vectorize import chunk_documents, generate_embeddings, save_embeddings_to_db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User
from app.models.search_session import SearchSession
from app.models.session_action import SessionAction
from app.tasks.celery_app import app


@app.task(bind=True, acks_late=True, max_retries=3, default_retry_delay=30)
def process_document_task(self, document_id: int) -> dict:
    """Process an ingested document: chunk, embed, and persist vectors.

    Args:
        document_id: Primary key of the Document to process.

    Returns:
        Status dictionary summarizing the processing outcome.
    """
    document: Document | None = None  # guard: db.get() may raise before assignment
    db: Session = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if not document:
            return {"status": "error", "reason": f"Document {document_id} not found"}

        if not document.content:
            document.status = "error"
            db.commit()
            return {"status": "error", "reason": "Document has no content to process"}

        # --- Idempotency guard ---
        # If chunks already exist for this document (e.g. a prior run crashed after
        # chunk_documents() committed but before generate_embeddings() finished),
        # skip re-chunking to avoid duplicate rows. Re-embed any chunks missing embeddings.
        existing_chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()
        if existing_chunks:
            chunks_needing_embeddings = [c for c in existing_chunks if c.embedding is None]
            if not chunks_needing_embeddings:
                # Already fully processed — mark and return immediately.
                document.status = "processed"
                db.commit()
                return {"status": "skipped", "document_id": document_id, "reason": "already_processed"}
            # Partially processed: only re-embed the chunks that are missing embeddings.
            chunks = chunks_needing_embeddings
        else:
            document.status = "processing"
            db.commit()

            docs = [document]
            chunks = chunk_documents(db, docs, chunk_size_tokens=450, overlap_tokens=50)

            if not chunks:
                document.status = "completed"
                db.commit()
                return {"status": "completed", "document_id": document_id, "chunks_created": 0}

        embeddings = generate_embeddings(chunks)
        save_embeddings_to_db(db, chunks, embeddings)

        document.status = "processed"
        db.commit()

        return {
            "status": "completed",
            "document_id": document_id,
            "chunks_created": len(chunks),
            "embedding_dimension": int(embeddings.shape[1]) if embeddings.size else 0,
        }
    except Exception as exc:
        try:
            # Rollback first: if the exception came from a DB operation, the session
            # is in a PendingRollback state and db.commit() would raise a secondary
            # exception masking the original.
            db.rollback()
        except Exception:
            pass  # best-effort cleanup — do not let secondary exception mask original
            
        # Retry up to max_retries times with exponential-ish back-off.
        # acks_late ensures the message is not acknowledged until this function
        # returns cleanly, so a crash before raise will redeliver — but the
        # idempotency guard above prevents chunk duplication on redelivery.
        from celery.exceptions import MaxRetriesExceededError
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            try:
                if document is not None:
                    # Refresh document from db to avoid stale state
                    document = db.get(Document, document_id)
                    if document:
                        document.status = "error"
                        db.commit()
            except Exception:
                pass
            raise
    finally:
        db.close()
