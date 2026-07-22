#!/usr/bin/env python3
"""Execution script for the biomedical ingestion and vectorization pipeline."""

from __future__ import annotations

import argparse
import sys

from app.core.security import hash_password
from app.data_pipeline.ingest import PubMedIngestor
from app.data_pipeline.vectorize import run_vectorization
from app.models import Base, SessionLocal, engine
from app.models.document import Document
from app.models.search_session import SearchSession
from app.models.user import User


def ensure_system_user(db_session) -> User:
    """Get or create a system user for pipeline ingestion."""
    user = db_session.query(User).filter(User.email == "system@biosearchai.local").first()
    if not user:
        user = User(
            email="system@biosearchai.local",
            hashed_password=hash_password("pipeline-system-user"),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BioSearchAI data pipeline")
    parser.add_argument("--query", default="TP53 gene mutation", help="PubMed search query")
    parser.add_argument("--top-n", type=int, default=5, help="Number of PubMed articles to fetch")
    parser.add_argument("--provider-email", default="researcher@institute.edu", help="NCBI Entrez email")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("[1/4] Ensuring schema and system user...")
        Base.metadata.create_all(bind=engine)

        user = ensure_system_user(db)
        session = SearchSession(
            user_id=user.id,
            session_name=f"Pipeline: {args.query}",
            query_summary=args.query,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        print(f"       Session ID: {session.id}")

        print(f"[2/4] Fetching PubMed abstracts for query: {args.query!r}")
        ingestor = PubMedIngestor(email=args.provider_email, db=db)
        records = ingestor.search(query=args.query, top_n=args.top_n)
        print(f"       Found {len(records)} records")

        print("[3/4] Saving documents...")
        saved = ingestor.save(records, session_id=session.id)
        print(f"       Saved {saved} new documents")

        print("[4/4] Chunking, embedding, and persisting to pgvector...")
        result = run_vectorization()
        print(f"       Status: {result.get('status')}")
        if result.get("status") == "completed":
            print(f"       Documents chunked: {result.get('documents_chunked')}")
            print(f"       Chunks created: {result.get('chunks_created')}")
            print(f"       Embedding model: {result.get('model')}")
            print(f"       Embedding dimension: {result.get('embedding_dimension')}")

        print("Pipeline completed successfully.")
        return 0
    except Exception as exc:
        print(f"Pipeline failed: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
