from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from mosaic_memory_api.domain.events import Source


class SourceSettingUpdate(BaseModel):
    enabled: bool


class SourceSettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: Source
    enabled: bool
    updated_at: datetime
    model_id: str
    model_label: str
    modality: str


class DeletionResult(BaseModel):
    deleted_count: int = Field(ge=0)
    scope: str
    audit_action: str


class GlobalEraseRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=100)


class GlobalEraseResult(BaseModel):
    raw_events_deleted: int = Field(ge=0)
    derived_memories_deleted: int = Field(ge=0)
    embeddings_deleted: int = Field(ge=0)
    graph_links_deleted: int = Field(ge=0)
    audit_logs_deleted: int = Field(ge=0)
    sources_disabled: int = Field(ge=0)
    vacuum_performed: bool
