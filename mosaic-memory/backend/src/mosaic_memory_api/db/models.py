from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from mosaic_memory_api.db.base import Base
from mosaic_memory_api.db.types import UtcDateTime


def utc_now() -> datetime:
    return datetime.now(UTC)


class RawEvent(Base):
    __tablename__ = "raw_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    privacy_level: Mapped[str] = mapped_column(String(30))
    retention_class: Mapped[str] = mapped_column(String(30))


class DerivedMemory(Base):
    """A local, deterministic summary built from one or more raw events."""

    __tablename__ = "derived_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        default=utc_now,
        index=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), index=True)
    summary: Mapped[str] = mapped_column(String(600))
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)


class MemoryEvidence(Base):
    """The raw-event evidence supporting a derived memory."""

    __tablename__ = "memory_evidence"
    __table_args__ = (UniqueConstraint("memory_id", "event_id"),)

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("derived_memories.id", ondelete="CASCADE"),
        index=True,
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("raw_events.id", ondelete="CASCADE"),
        index=True,
    )


class MemoryEmbedding(Base):
    """A transparent, on-device feature-hash vector for local retrieval."""

    __tablename__ = "memory_embeddings"

    memory_id: Mapped[str] = mapped_column(
        ForeignKey("derived_memories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    model: Mapped[str] = mapped_column(String(100))
    dimensions: Mapped[int] = mapped_column(Integer)
    vector: Mapped[list[float]] = mapped_column(JSON, default=list)


class MemoryLink(Base):
    """A lightweight graph edge between memories that share meaningful terms."""

    __tablename__ = "memory_links"
    __table_args__ = (
        UniqueConstraint("source_memory_id", "target_memory_id", "relation"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    source_memory_id: Mapped[str] = mapped_column(
        ForeignKey("derived_memories.id", ondelete="CASCADE"),
        index=True,
    )
    target_memory_id: Mapped[str] = mapped_column(
        ForeignKey("derived_memories.id", ondelete="CASCADE"),
        index=True,
    )
    relation: Mapped[str] = mapped_column(String(50))
    shared_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)


class SourceSetting(Base):
    __tablename__ = "source_settings"

    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        default=utc_now,
        onupdate=utc_now,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime(),
        default=utc_now,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    deleted_count: Mapped[int] = mapped_column(Integer, default=0)
