from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from mosaic_memory_api.domain.events import EventRead


class TabContextRequest(BaseModel):
    """A user-triggered, privacy-bounded excerpt from the active browser tab."""

    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    title: str = Field(min_length=1, max_length=500)
    host: str = Field(min_length=1, max_length=253)
    path: str = Field(min_length=1, max_length=1_000)
    description: str | None = Field(default=None, max_length=2000)
    context_text: str = Field(default="", max_length=6_000)

    # Optional source-specific fields
    source: str = Field(default="browser", pattern=r"^(browser|youtube|document)$")
    video_id: str | None = Field(default=None, max_length=64)
    channel: str | None = Field(default=None, max_length=200)
    has_transcript: bool = Field(default=False)

    @field_validator("host")
    @classmethod
    def host_must_not_include_a_url_or_port(cls, value: str) -> str:
        normalized = value.lower().strip()
        if "/" in normalized or ":" in normalized or "?" in normalized:
            raise ValueError("host must not include a URL, port, or query string.")
        return normalized

    @field_validator("path")
    @classmethod
    def path_must_not_include_query_data(cls, value: str) -> str:
        normalized = value.strip()
        if "?" in normalized or "#" in normalized:
            raise ValueError("path must exclude query strings and fragments.")
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        return normalized

    @field_validator("context_text")
    @classmethod
    def normalize_context_text(cls, value: str) -> str:
        return " ".join(value.split())


class TabContextResponse(BaseModel):
    event: EventRead
    model_id: str
    summary: str
    topics: list[str]
