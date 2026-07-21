from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class Document(Base):
    """Document ingested into a search session for RAG."""

    __tablename__ = "documents"

    id: int = Column(Integer, primary_key=True, index=True)
    session_id: int = Column(Integer, ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False)
    title: str = Column(String(512), nullable=False)
    source_url: Optional[str] = Column(String(1024), nullable=True)
    source_type: str = Column(String(50), nullable=False)
    ingested_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    session = relationship("SearchSession", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
