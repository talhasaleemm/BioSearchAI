from typing import Optional

from sqlalchemy import Index, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import TSVECTOR, ARRAY
from sqlalchemy.types import Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Chunk(Base):
    """Text chunk associated with a document for retrieval."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(ARRAY(Float), nullable=True)
    chunk_metadata: Mapped[Optional[dict]] = mapped_column("metadata_json", JSON, nullable=True)
    fts_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index(
            "ix_chunk_fts",
            "fts_vector",
            postgresql_using="gin",
        ),
    )
