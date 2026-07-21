from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class SessionAction(Base):
    """Individual step within a search session (query, retrieval, answer)."""

    __tablename__ = "session_actions"

    id: int = Column(Integer, primary_key=True, index=True)
    session_id: int = Column(Integer, ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False)
    timestamp: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    input_query: str = Column(Text, nullable=False)
    retrieved_evidence: Optional[dict] = Column(JSON, nullable=True)
    extracted_entities: Optional[dict] = Column(JSON, nullable=True)
    generated_answer: Optional[str] = Column(Text, nullable=True)

    session = relationship("SearchSession", back_populates="actions")
