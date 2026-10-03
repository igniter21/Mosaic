from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class Source(str, Enum):
    BROWSER = "browser"
    YOUTUBE = "youtube"
    LEETCODE = "leetcode"
    VSCODE = "vscode"
    DOCUMENT = "document"
    GIT = "git"


class PrivacyLevel(str, Enum):
    NORMAL = "normal"
    SENSITIVE = "sensitive"


class RetentionClass(str, Enum):
    TEMPORARY = "temporary"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: Source
    event_type: str = Field(min_length=2, max_length=100)
    title: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)
    privacy_level: PrivacyLevel = PrivacyLevel.NORMAL
    retention_class: RetentionClass = RetentionClass.SHORT_TERM


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: UUID = Field(validation_alias="id")
    occurred_at: datetime
    source: Source
    event_type: str
    title: str | None
    payload: dict[str, Any]
    privacy_level: PrivacyLevel
    retention_class: RetentionClass
    visit_count: int = 1
    first_seen_at: datetime | None = None
