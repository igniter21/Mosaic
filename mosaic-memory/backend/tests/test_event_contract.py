from datetime import UTC, datetime
from uuid import uuid4

import pytest

from mosaic_memory_api.domain.events import EventCreate, Source


@pytest.mark.parametrize(
    ("source", "event_type", "payload"),
    [
        ("browser", "page_viewed", {"host": "example.com", "path": "/guide"}),
        (
            "youtube",
            "video_viewed",
            {"video_id": "dQw4w9WgXcQ", "host": "youtube.com"},
        ),
        (
            "leetcode",
            "problem_viewed",
            {"problem_slug": "two-sum", "host": "leetcode.com"},
        ),
        (
            "vscode",
            "document_saved",
            {"language_id": "python", "relative_path": "src/app.py"},
        ),
        ("document", "document_indexed", {"extension": ".pdf", "size_bytes": 128}),
    ],
)
def test_collector_event_shapes_match_the_ingestion_contract(
    source: str,
    event_type: str,
    payload: dict[str, object],
) -> None:
    event = EventCreate.model_validate(
        {
            "event_id": uuid4(),
            "occurred_at": datetime.now(UTC),
            "source": source,
            "event_type": event_type,
            "title": "Example activity",
            "payload": payload,
            "privacy_level": "normal",
            "retention_class": "short_term",
        }
    )

    assert event.source is Source(source)
    assert event.event_type == event_type
    assert event.payload == payload
