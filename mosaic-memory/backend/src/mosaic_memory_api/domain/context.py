from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from mosaic_memory_api.domain.events import EventRead, Source


class ContextAskRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=8, ge=1, le=20)
    project_id: str | None = None
    goal_id: str | None = None
    source: Source | None = None
    agent_name: str = "default"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    repository: str | None = Field(default=None, max_length=500)
    workspace_name: str | None = Field(default=None, max_length=300)


class ProjectRead(BaseModel):
    id: str
    name: str
    slug: str
    repository: str | None
    workspace_name: str | None
    last_seen_at: datetime


class GoalCreate(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(default="", max_length=1000)
    project_id: str | None = None


class GoalUpdate(BaseModel):
    status: str | None = Field(default=None, min_length=2, max_length=30)
    description: str | None = Field(default=None, max_length=1000)


class GoalRead(BaseModel):
    id: str
    title: str
    description: str
    status: str
    project_id: str | None
    created_at: datetime
    completed_at: datetime | None


class SessionRead(BaseModel):
    id: str
    started_at: datetime
    ended_at: datetime
    project_id: str | None
    summary: str
    source_count: int
    event_count: int
    focus_score: float
    goal_hint: str | None
    event_ids: list[str] = Field(default_factory=list)


class SessionDetailRead(SessionRead):
    events: list[EventRead] = Field(default_factory=list)


class ContextResult(BaseModel):
    query: str
    answer: str
    project_id: str | None
    goal_id: str | None
    retrieval_method: str
    memories: list[dict[str, Any]]
    active_session: SessionRead | None = None
    evidence_receipt: dict[str, Any]
    generated_at: datetime


class LearningConcept(BaseModel):
    concept: str
    exposure_count: int
    practice_count: int
    implementation_count: int
    revision_count: int
    sources: list[str]
    first_seen_at: datetime | None
    last_seen_at: datetime | None


class LearningGraphRead(BaseModel):
    concepts: list[LearningConcept]
    suggestions: list[str]


class ContextPolicyUpsert(BaseModel):
    agent_name: str = Field(min_length=2, max_length=200)
    allowed_sources: list[Source] = Field(default_factory=list)
    denied_sources: list[Source] = Field(default_factory=list)
    allowed_projects: list[str] = Field(default_factory=list)
    deny_sensitive: bool = True
    allow_external: bool = False


class ContextPolicyRead(BaseModel):
    agent_name: str
    allowed_sources: list[str]
    denied_sources: list[str]
    allowed_projects: list[str]
    deny_sensitive: bool
    allow_external: bool
    updated_at: datetime


class CapsuleCreate(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    project_id: str | None = None
    goal_id: str | None = None
    limit: int = Field(default=12, ge=1, le=30)
    agent_name: str = "default"
    expires_at: datetime | None = None


class CapsuleRead(BaseModel):
    id: str
    title: str
    project_id: str | None
    goal_id: str | None
    created_at: datetime
    expires_at: datetime | None
    payload: dict[str, Any]


class LifecyclePreview(BaseModel):
    expired_memory_ids: list[str]
    temporary_candidates: int
    short_term_candidates: int
    protected_pinned: int


class LifecycleRunRequest(BaseModel):
    execute: bool = False


class LifecycleRunResult(BaseModel):
    deleted_memory_count: int
    deleted_event_count: int
    dry_run: bool


class PrivacyLedgerRead(BaseModel):
    occurred_at: datetime
    direction: str
    provider: str
    action: str
    source: str | None
    bytes_count: int
    reason: str
    metadata: dict[str, Any]

class ResumeContextRead(BaseModel):
    title: str
    summary: str

    session: SessionRead | None = None
    project: ProjectRead | None = None
    goals: list[GoalRead] = Field(
        default_factory=list
    )

    memories: list[dict[str, Any]] = Field(
        default_factory=list
    )

    suggested_next_steps: list[str] = Field(
        default_factory=list
    )

    evidence_receipt: dict[str, Any] = Field(
        default_factory=dict
    )

    generated_at: datetime