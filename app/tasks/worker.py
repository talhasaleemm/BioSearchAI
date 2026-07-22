"""Background worker tasks for BioSearchAI."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.data_pipeline.vectorize import chunk_documents, generate_embeddings, save_embeddings_to_db
from app.models.document import Document
from app.tasks.celery_app import app


@app.task(bind=True)
def process_document_task(self, document_id: int) -> dict:
    """Process an ingested document: chunk, embed, and persist vectors.

    Args:
        document_id: Primary key of the Document to process.

    Returns:
        Status dictionary summarizing the processing outcome.
    """
    db: Session = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if not document:
            return {"status": "error", "reason": f"Document {document_id} not found"}

        if not document.content:
            document.status = "error"
            db.commit()
            return {"status": "error", "reason": "Document has no content to process"}

        document.status = "processing"
        db.commit()

        docs = [document]
        chunks = chunk_documents(db, docs, chunk_size_tokens=450, overlap_tokens=50)

        if not chunks:
            document.status = "completed"
            db.commit()
            return {"status": "completed", "document_id": document_id, "chunks_created": 0}

        embeddings = generate_embeddings(chunks, model_name="pritamdeka/S-PubMedBert-MS-MARCO")
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
        if db.is_active:
            document.status = "error"
            db.commit()
        raise exc
    finally:
        db.close()
