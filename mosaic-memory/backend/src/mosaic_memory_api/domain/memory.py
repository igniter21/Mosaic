from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from mosaic_memory_api.domain.events import EventRead, Source


class AskMemoryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)


class MemoryEvidenceRead(BaseModel):
    event: EventRead


class MemoryLinkRead(BaseModel):
    memory_id: UUID
    relation: str
    shared_keywords: list[str]


class DerivedMemoryRead(BaseModel):
    id: UUID
    occurred_at: datetime
    source: Source
    summary: str
    keywords: list[str]
    model_id: str
    score: float = Field(ge=0, le=1)
    evidence: list[MemoryEvidenceRead]
    links: list[MemoryLinkRead]


class AskMemoryResponse(BaseModel):
    query: str
    answer: str
    retrieval_method: str
    memories: list[DerivedMemoryRead]
    generated_at: datetime


class DerivedMemoryModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    occurred_at: datetime
    source: Source
    summary: str
    keywords: list[str]
