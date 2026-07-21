from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from app.models.base import Base


class User(Base):
    """User account model for authentication and session tracking."""

    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    email: str = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password: str = Column(String(255), nullable=False)
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    search_sessions: list["SearchSession"] = relationship(
        "SearchSession", back_populates="user", cascade="all, delete-orphan"
    )
