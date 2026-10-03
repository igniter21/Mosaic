from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mosaic_memory_api.db.base import Base


class SemanticEmbedding(Base):
    __tablename__ = "semantic_embeddings"
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("derived_memories.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(200))
    dimensions: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list[float]] = mapped_column(JSON, default=list)
