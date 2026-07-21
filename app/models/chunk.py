from typing import Optional

from sqlalchemy import Column, Integer, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base


class Chunk(Base):
    """Text chunk associated with a document for retrieval."""

    __tablename__ = "chunks"

    id: int = Column(Integer, primary_key=True, index=True)
    document_id: int = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    text: str = Column(Text, nullable=False)
    chunk_index: int = Column(Integer, nullable=False)
    embedding: Optional[list[float]] = Column(JSON, nullable=True)
    metadata: Optional[dict] = Column("metadata_json", JSON, nullable=True)

    document = relationship("Document", back_populates="chunks")
