from sqlalchemy import select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.models import RawEvent
from mosaic_memory_api.domain.events import EventCreate, Source
from mosaic_memory_api.services.memory_service import build_memory_for_event
from mosaic_memory_api.services.privacy_service import (
    SourceDisabledError,
    source_is_enabled,
)


def create_event(db: Session, event: EventCreate) -> RawEvent:
    if not source_is_enabled(db, event.source):
        raise SourceDisabledError(
            f"The {event.source.value} source is currently disabled."
        )

    existing_event = db.get(RawEvent, str(event.event_id))

    if existing_event:
        build_memory_for_event(db, existing_event)
        db.commit()
        return existing_event

    raw_event = RawEvent(
        id=str(event.event_id),
        occurred_at=event.occurred_at,
        source=event.source.value,
        event_type=event.event_type,
        title=event.title,
        payload=event.payload,
        privacy_level=event.privacy_level.value,
        retention_class=event.retention_class.value,
    )

    db.add(raw_event)
    db.flush()
    build_memory_for_event(db, raw_event)
    db.commit()
    db.refresh(raw_event)

    return raw_event


def list_events(
    db: Session,
    *,
    limit: int,
    offset: int,
    source: Source | None = None,
) -> list[RawEvent]:
    statement = select(RawEvent)

    if source is not None:
        statement = statement.where(RawEvent.source == source.value)

    statement = (
        statement
        .order_by(RawEvent.occurred_at.desc())
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())
