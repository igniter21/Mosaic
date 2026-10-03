from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
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


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    repository: Mapped[str | None] = mapped_column(String(500), nullable=True)
    workspace_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=utc_now, index=True
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=utc_now, index=True
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    title: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=utc_now, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class ActivitySession(Base):
    __tablename__ = "activity_sessions"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    started_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    ended_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    summary: Mapped[str] = mapped_column(String(1000))
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    focus_score: Mapped[float] = mapped_column(Float, default=0.0)
    goal_hint: Mapped[str | None] = mapped_column(String(300), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class SessionEvent(Base):
    __tablename__ = "session_events"
    __table_args__ = (UniqueConstraint("session_id", "event_id"),)
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("activity_sessions.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("raw_events.id", ondelete="CASCADE"), index=True
    )


class ProjectMemory(Base):
    __tablename__ = "project_memories"
    __table_args__ = (UniqueConstraint("project_id", "memory_id"),)
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("derived_memories.id", ondelete="CASCADE"), index=True
    )


class GoalMemory(Base):
    __tablename__ = "goal_memories"
    __table_args__ = (UniqueConstraint("goal_id", "memory_id"),)
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    goal_id: Mapped[str] = mapped_column(
        ForeignKey("goals.id", ondelete="CASCADE"), index=True
    )
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("derived_memories.id", ondelete="CASCADE"), index=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.5)


class MemoryLifecycle(Base):
    __tablename__ = "memory_lifecycle"
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("derived_memories.id", ondelete="CASCADE"), primary_key=True
    )
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime(), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime(), nullable=True, index=True
    )
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(300), default="automatic")


class ContextPolicy(Base):
    __tablename__ = "context_policies"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    agent_name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    allowed_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    denied_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_projects: Mapped[list[str]] = mapped_column(JSON, default=list)
    deny_sensitive: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_external: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=utc_now, onupdate=utc_now
    )


class ContextCapsule(Base):
    __tablename__ = "context_capsules"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    title: Mapped[str] = mapped_column(String(300), index=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    goal_id: Mapped[str | None] = mapped_column(
        ForeignKey("goals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=utc_now, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime(), nullable=True, index=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class PrivacyLedgerEntry(Base):
    __tablename__ = "privacy_ledger"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=utc_now, index=True
    )
    direction: Mapped[str] = mapped_column(String(20), index=True)
    provider: Mapped[str] = mapped_column(String(100), default="local")
    action: Mapped[str] = mapped_column(String(200))
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bytes_count: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(String(500), default="")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
