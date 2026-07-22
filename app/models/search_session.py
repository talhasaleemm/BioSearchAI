from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class SearchSession(Base):
    """Top-level search session representing a conversation or research task."""

    __tablename__ = "search_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    query_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="search_sessions")
    actions: Mapped[list["SessionAction"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="session", cascade="all, delete-orphan")
