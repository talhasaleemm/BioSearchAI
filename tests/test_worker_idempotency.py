"""Test idempotency of process_document_task under simulated crash-redelivery scenarios.

Tests call process_document_task.apply() directly (Celery eager execution) and mock
generate_embeddings + save_embeddings_to_db so no live model or FAISS is required.
"""
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, call, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.db import Base
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.search_session import SearchSession
from app.models.user import User
from app.tasks.worker import process_document_task
# Import all models to fully populate the SQLAlchemy mapper registry
import app.models.session_action  # noqa: F401

settings = get_settings()

pytestmark = pytest.mark.skipif(
    not settings.DATABASE_URL or "localhost" in settings.DATABASE_URL,
    reason="Live PostgreSQL container required",
)

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Fake embedding array returned by the mocked generate_embeddings
_FAKE_DIM = 768
_FAKE_EMBEDDINGS = np.zeros((2, _FAKE_DIM), dtype="float32")


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_document(db, content="Aspirin reduces inflammation in patients."):
    """Create the full User → SearchSession → Document FK chain."""
    import uuid
    user = User(email=f"t_{uuid.uuid4().hex[:8]}@test.com", hashed_password="x")
    db.add(user)
    db.flush()
    sess = SearchSession(user_id=user.id)
    db.add(sess)
    db.flush()
    doc = Document(
        session_id=sess.id,
        title="Test doc",
        content=content,
        source_type="test",
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ─── Test 1: all chunks exist, all already embedded → task returns "skipped" ──

def test_task_skips_fully_processed_document(db):
    """
    Simulates redelivery of a message for an already-fully-processed document.
    Guard must return 'skipped' immediately without calling generate_embeddings
    or save_embeddings_to_db.
    """
    doc = _make_document(db)

    vec = np.zeros(_FAKE_DIM, dtype="float32").tolist()
    c1 = Chunk(document_id=doc.id, text="Aspirin.", chunk_index=0, embedding=vec)
    db.add(c1)
    db.commit()

    with patch("app.tasks.worker.generate_embeddings") as mock_embed, \
         patch("app.tasks.worker.save_embeddings_to_db") as mock_save:

        result = process_document_task.apply(args=[doc.id])

    assert result.successful(), f"Task failed unexpectedly: {result.result}"
    ret = result.get()
    assert ret["status"] == "skipped", f"Expected 'skipped', got: {ret}"
    assert ret["reason"] == "already_processed"

    mock_embed.assert_not_called()
    mock_save.assert_not_called()

    # Cleanup
    db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
    db.query(Document).filter(Document.id == doc.id).delete()
    db.commit()


# ─── Test 2: chunks exist but no embeddings → task re-embeds them ─────────────

def test_task_reembeds_chunks_on_redelivery(db):
    """
    Simulates redelivery after a crash that happened after chunk_documents() committed
    but before save_embeddings_to_db() ran. The idempotency guard must:
    - NOT re-chunk (no new Chunk rows)
    - Call generate_embeddings exactly once with the un-embedded chunks
    - Call save_embeddings_to_db exactly once
    - Return status 'completed'
    """
    doc = _make_document(db)

    c1 = Chunk(document_id=doc.id, text="Aspirin reduces inflammation.", chunk_index=0, embedding=None)
    c2 = Chunk(document_id=doc.id, text="in patients.", chunk_index=1, embedding=None)
    db.add_all([c1, c2])
    db.commit()
    # Capture IDs for assertion
    chunk_ids = {c1.id, c2.id}

    with patch("app.tasks.worker.generate_embeddings",
               return_value=_FAKE_EMBEDDINGS) as mock_embed, \
         patch("app.tasks.worker.save_embeddings_to_db") as mock_save:

        # Capture IDs eagerly inside the mock call before the task's session closes
        captured_ids: list[set] = []
        original_embed = mock_embed.side_effect

        def _capture_and_return(chunks, **kwargs):
            captured_ids.append({c.id for c in chunks})
            return _FAKE_EMBEDDINGS

        mock_embed.side_effect = _capture_and_return

        result = process_document_task.apply(args=[doc.id])

    assert result.successful(), f"Task failed unexpectedly: {result.result}"
    ret = result.get()
    assert ret["status"] == "completed", f"Expected 'completed', got: {ret}"

    # generate_embeddings called exactly once with the correct chunk IDs
    assert len(captured_ids) == 1, f"Expected 1 call to generate_embeddings, got {len(captured_ids)}"
    assert captured_ids[0] == chunk_ids, (
        f"Expected generate_embeddings called with chunks {chunk_ids}, "
        f"got {captured_ids[0]}"
    )

    # save_embeddings_to_db called exactly once
    mock_save.assert_called_once()

    # Chunk count must NOT have increased
    post_count = db.query(Chunk).filter(Chunk.document_id == doc.id).count()
    assert post_count == 2, f"Expected 2 chunks, got {post_count} (re-chunking occurred)"

    # Cleanup
    db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
    db.query(Document).filter(Document.id == doc.id).delete()
    db.commit()


# ─── Test 3: exception during save_embeddings_to_db → error status, no masking ─

def test_exception_in_save_sets_error_status_without_masking(db):
    """
    Simulates a failure inside save_embeddings_to_db (e.g. DB timeout).
    Confirms:
    - document.status is set to 'error' in the DB
    - The original exception propagates (not masked by a secondary PendingRollbackError)
    - The task result is marked failed
    """
    doc = _make_document(db)

    with patch("app.tasks.worker.generate_embeddings", return_value=_FAKE_EMBEDDINGS), \
         patch("app.tasks.worker.save_embeddings_to_db",
               side_effect=RuntimeError("simulated save failure")) as mock_save:

        result = process_document_task.apply(args=[doc.id])

    assert result.failed(), "Expected task to fail"
    # The propagated exception must be the original RuntimeError, not a SQLAlchemy
    # PendingRollbackError or AttributeError masking it
    assert isinstance(result.result, RuntimeError), (
        f"Expected RuntimeError, got {type(result.result)}: {result.result}"
    )
    assert "simulated save failure" in str(result.result)

    # Verify DB state: document should be marked 'error'
    fresh_db = TestSessionLocal()
    try:
        updated_doc = fresh_db.get(Document, doc.id)
        assert updated_doc.status == "error", (
            f"Expected document status 'error', got '{updated_doc.status}'"
        )
    finally:
        fresh_db.close()

    # Cleanup
    db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
    db.query(Document).filter(Document.id == doc.id).delete()
    db.commit()
