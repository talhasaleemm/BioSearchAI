"""End-to-end integration tests for BioSearchAI RAG pipeline."""

from __future__ import annotations

import json
import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.db import Base, get_db
from app.main import app
from app.models.document import Document
from app.models.search_session import SearchSession
from app.models.user import User

settings = get_settings()

pytestmark = pytest.mark.skipif(
    not settings.DATABASE_URL or "localhost" in settings.DATABASE_URL,
    reason="Live PostgreSQL container required for E2E tests",
)

OPENAI_KEY = os.getenv("OPENAI_API_KEY")

_PLACEHOLDER_KEYS = {"test-key", "sk-replace-me", None}

def _has_real_openai_key() -> bool:
    """Return True if OPENAI_API_KEY is real, or if pointing to local Ollama."""
    if "host.docker.internal" in settings.OPENAI_API_BASE or "localhost" in settings.OPENAI_API_BASE:
        return True
    
    if OPENAI_KEY is None:
        return False
    # Treat obvious placeholder / CI stubs as absent
    if OPENAI_KEY in _PLACEHOLDER_KEYS or OPENAI_KEY.startswith("sk-replace"):
        return False
    return True

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Session-scoped schema: create tables once, drop once at the very end ──────
@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    """Create all tables once before the test session starts; drop after all tests finish.

    This replaces the previous per-test drop_all/create_all, which caused a
    synchronous DDL AccessExclusiveLock contention deadlock during teardown.
    """
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ── Module-level reference to the current test's Connection ──────────────────
# Pytest runs tests sequentially (single-threaded), so this is never contested.
_current_test_connection = None


# ── FastAPI dependency override: reuse the current test connection ────────────
def _override_get_db():
    """FastAPI dependency that returns a Session bound to the current test's
    Connection (if active), so endpoint code shares the same transaction as
    the test fixture — without sharing a single Session object across threads.

    Falls back to an independent session for tests that don't use db_session.
    """
    if _current_test_connection is not None:
        db = Session(bind=_current_test_connection)
        try:
            yield db
        finally:
            db.close()
    else:
        # Tests without db_session (e.g. test_search_empty_query_returns_400)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()


app.dependency_overrides[get_db] = _override_get_db


# ── Per-test rollback: wrap each test in a transaction, always roll back ──────
@pytest.fixture(scope="function")
def db_session() -> Iterator[Session]:
    """Yield a Session bound to a transaction that is ALWAYS rolled back.

    Each consumer (test code and endpoint dependency) gets its own Session
    object but they share the same underlying Connection/transaction, so they
    see each other's writes without any data persisting between tests.
    No DDL is executed per-test; schema is managed at session scope by _schema.
    """
    global _current_test_connection
    connection = engine.connect()
    transaction = connection.begin()
    _current_test_connection = connection
    db = Session(bind=connection)
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()
        _current_test_connection = None


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    user = User(
        email="e2e-test@biosearchai.local",
        hashed_password="test-hash",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_session(db_session: Session, test_user: User) -> SearchSession:
    session = SearchSession(
        user_id=test_user.id,
        session_name="E2E Test Session",
        query_summary="TP53 gene mutation",
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


@pytest.fixture(scope="function")
def test_document(db_session: Session, test_session: SearchSession) -> Document:
    doc = Document(
        session_id=test_session.id,
        title="TP53 in Human Cancers",
        source_url="https://pubmed.ncbi.nlm.nih.gov/12345/",
        source_type="pubmed",
        content=(
            "TP53 is a tumor suppressor gene. Mutations in TP53 are found in about 50% of human cancers. "
            "The protein p53 regulates the cell cycle and prevents cancer formation. "
            "Methods: We performed RNA-seq analysis on 200 patient samples. "
            "Western blot confirmed protein expression levels using antibodies against TP53. "
            "Results: TP53 expression was significantly reduced in tumor tissue compared to normal controls."
        ),
        status="pending",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


def test_health_endpoint(db_session: Session) -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_search_empty_query_returns_400() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/search", json={"query": "   ", "top_k": 5})
        assert response.status_code == 400
        assert response.json()["detail"] == "Query must not be empty."


@pytest.mark.asyncio
async def test_retrieval_pipeline(db_session: Session, test_document: Document) -> None:
    from app.data_pipeline.vectorize import chunk_documents, generate_embeddings, save_embeddings_to_db
    from app.services.retrieval import VectorRetriever

    chunks = chunk_documents(db_session, [test_document], chunk_size_tokens=100, overlap_tokens=20)
    assert len(chunks) >= 1

    embeddings = generate_embeddings(chunks, model_name=settings.EMBEDDING_MODEL_PATH)
    save_embeddings_to_db(db_session, chunks, embeddings)

    retriever = VectorRetriever()
    results = await retriever.search_similar_chunks(db=db_session, query="TP53 tumor suppressor", top_k=5)

    assert len(results) >= 1
    for chunk, document, score in results:
        assert chunk.text
        assert score >= 0.0
        assert document.id == test_document.id
        assert "TP53" in chunk.text or "tumor" in chunk.text.lower()


@pytest.mark.skipif(not _has_real_openai_key(), reason="Real OPENAI_API_KEY required for E2E LLM tests")
@pytest.mark.asyncio
async def test_llm_generation(db_session: Session, test_document: Document) -> None:
    from app.data_pipeline.vectorize import chunk_documents, generate_embeddings, save_embeddings_to_db
    from app.services.rag import RAGEngine

    chunks = chunk_documents(db_session, [test_document], chunk_size_tokens=100, overlap_tokens=20)
    embeddings = generate_embeddings(chunks, model_name=settings.EMBEDDING_MODEL_PATH)
    save_embeddings_to_db(db_session, chunks, embeddings)

    rag_engine = RAGEngine()
    response = await rag_engine.generate_answer(db=db_session, query="What is the role of TP53 in cancer?", top_k=3)

    assert response.query == "What is the role of TP53 in cancer?"
    assert response.answer
    assert len(response.answer.strip()) > 20
    assert len(response.sources) >= 1
    for source in response.sources:
        assert source.text
        assert source.document is not None
        assert source.document.title == "TP53 in Human Cancers"


@pytest.mark.skipif(not _has_real_openai_key(), reason="Real OPENAI_API_KEY required for E2E LLM tests")
def test_rag_stream_endpoint(db_session: Session, test_document: Document) -> None:
    from app.data_pipeline.vectorize import chunk_documents, generate_embeddings, save_embeddings_to_db

    chunks = chunk_documents(db_session, [test_document], chunk_size_tokens=100, overlap_tokens=20)
    embeddings = generate_embeddings(chunks, model_name=settings.EMBEDDING_MODEL_PATH)
    save_embeddings_to_db(db_session, chunks, embeddings)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/rag/stream",
            json={"query": "What is the role of TP53 in cancer?", "top_k": 3},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.text

    assert "data:" in body
    assert "TP53" in body or "cancer" in body.lower()
