from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class SearchSession(Base):
    """Top-level search session representing a conversation or research task."""

    __tablename__ = "search_sessions"

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_name: Optional[str] = Column(String(255), nullable=True)
    query_summary: Optional[str] = Column(String(500), nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="search_sessions")
    actions = relationship("SessionAction", back_populates="session", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="session", cascade="all, delete-orphan")
