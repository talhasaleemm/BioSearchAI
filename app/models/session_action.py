from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class SessionAction(Base):
    """Individual step within a search session (query, retrieval, answer)."""

    __tablename__ = "session_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("search_sessions.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    input_query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    extracted_entities: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    generated_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    session: Mapped["SearchSession"] = relationship(back_populates="actions")
