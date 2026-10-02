"""Persist one Gemini-understood browser context as evidence-backed local memory."""

from sqlalchemy.orm import Session

from mosaic_memory_api.db.models import RawEvent
from mosaic_memory_api.domain.events import (
    EventCreate,
    PrivacyLevel,
    RetentionClass,
    Source,
)
from mosaic_memory_api.domain.tab_context import TabContextRequest
from mosaic_memory_api.services.event_service import create_event
from mosaic_memory_api.services.gemini_service import (
    GeminiTabUnderstanding,
    understand_tab_context,
)

LOCAL_EVIDENCE_LIMIT = 2_500


def understand_and_store_tab(
    db: Session,
    request: TabContextRequest,
) -> tuple[RawEvent, GeminiTabUnderstanding]:
    """Call Gemini only for this explicit request, then keep bounded local evidence."""

    if request.source == "youtube":
        source = Source.YOUTUBE
    elif request.source == "document":
        source = Source.DOCUMENT
    else:
        source = Source.BROWSER

    understanding = understand_tab_context(request)

    payload: dict[str, object] = {
        "host": request.host,
        "path": request.path,
        "description": request.description,
        "context_summary": understanding.summary,
        "context_topics": understanding.topics,
        "context_excerpt": request.context_text[:LOCAL_EVIDENCE_LIMIT],
        "context_model": understanding.model_id,
    }

    # Include YouTube-specific metadata when present
    if source is Source.YOUTUBE:
        if request.video_id:
            payload["video_id"] = request.video_id
        if request.channel:
            payload["channel"] = request.channel
        payload["has_transcript"] = request.has_transcript

    event = EventCreate(
        event_id=request.event_id,
        occurred_at=request.occurred_at,
        source=source,
        event_type="tab_understood",
        title=request.title,
        payload=payload,
        privacy_level=PrivacyLevel.SENSITIVE,
        retention_class=RetentionClass.SHORT_TERM,
    )
    return create_event(db, event), understanding

