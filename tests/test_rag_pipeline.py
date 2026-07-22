"""End-to-end integration tests for BioSearchAI RAG pipeline."""

from __future__ import annotations

import json
import os
from typing import Generator

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

engine = create_engine(settings.DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
        Base.metadata.drop_all(bind=engine)


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


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db
client = TestClient(app)


def test_health_endpoint(db_session: Session) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_search_empty_query_returns_400() -> None:
    response = client.post("/api/v1/search", json={"query": "   ", "top_k": 5})
    assert response.status_code == 400
    assert response.json()["detail"] == "Query must not be empty."


def test_retrieval_pipeline(db_session: Session, test_document: Document) -> None:
    from app.data_pipeline.vectorize import chunk_documents, generate_embeddings, save_embeddings_to_db
    from app.services.retrieval import VectorRetriever

    chunks = chunk_documents(db_session, [test_document], chunk_size_tokens=100, overlap_tokens=20)
    assert len(chunks) >= 1

    embeddings = generate_embeddings(chunks, model_name="pritamdeka/S-PubMedBert-MS-MARCO")
    save_embeddings_to_db(db_session, chunks, embeddings)

    retriever = VectorRetriever()
    results = retriever.search_similar_chunks(db=db_session, query="TP53 tumor suppressor", top_k=5)

    assert len(results) >= 1
    for chunk, document, score in results:
        assert chunk.text
        assert score >= 0.0
        assert document.id == test_document.id
        assert "TP53" in chunk.text or "tumor" in chunk.text.lower()


@pytest.mark.skipif(OPENAI_KEY is None, reason="OPENAI_API_KEY is required for E2E LLM tests")
def test_llm_generation(db_session: Session, test_document: Document) -> None:
    from app.data_pipeline.vectorize import chunk_documents, generate_embeddings, save_embeddings_to_db
    from app.services.rag import RAGEngine

    chunks = chunk_documents(db_session, [test_document], chunk_size_tokens=100, overlap_tokens=20)
    embeddings = generate_embeddings(chunks, model_name="pritamdeka/S-PubMedBert-MS-MARCO")
    save_embeddings_to_db(db_session, chunks, embeddings)

    engine = RAGEngine()
    response = engine.generate_answer(db=db_session, query="What is the role of TP53 in cancer?", top_k=3)

    assert response.query == "What is the role of TP53 in cancer?"
    assert response.answer
    assert len(response.answer.strip()) > 20
    assert len(response.sources) >= 1
    for source in response.sources:
        assert source.text
        assert source.document is not None
        assert source.document.title == "TP53 in Human Cancers"


@pytest.mark.skipif(OPENAI_KEY is None, reason="OPENAI_API_KEY is required for E2E LLM tests")
def test_rag_stream_endpoint(db_session: Session, test_document: Document) -> None:
    from app.data_pipeline.vectorize import chunk_documents, generate_embeddings, save_embeddings_to_db

    chunks = chunk_documents(db_session, [test_document], chunk_size_tokens=100, overlap_tokens=20)
    embeddings = generate_embeddings(chunks, model_name="pritamdeka/S-PubMedBert-MS-MARCO")
    save_embeddings_to_db(db_session, chunks, embeddings)

    response = client.post(
        "/api/v1/rag/stream",
        json={"query": "What is the role of TP53 in cancer?", "top_k": 3},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "data:" in body
    assert "TP53" in body or "cancer" in body.lower()
