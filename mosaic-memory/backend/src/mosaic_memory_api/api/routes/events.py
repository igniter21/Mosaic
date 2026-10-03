import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from mosaic_memory_api.db.session import get_db
from mosaic_memory_api.domain.events import EventCreate, EventRead, Source
from mosaic_memory_api.domain.privacy import DeletionResult
from mosaic_memory_api.services.domain_policy_service import PrivacyPolicyDeniedError
from mosaic_memory_api.services.event_service import create_event, list_events
from mosaic_memory_api.services.privacy_service import (
    SourceDisabledError,
    delete_event_by_id,
    delete_events_by_filter,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def ingest_event(
    event: EventCreate,
    db: Session = Depends(get_db),
) -> EventRead:
    try:
        stored_event = create_event(db, event)
    except (SourceDisabledError, PrivacyPolicyDeniedError) as error:
        logger.warning(
            "Event rejected (403 Forbidden): %s (source=%s, type=%s)",
            error,
            event.source.value,
            event.event_type,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        ) from error

    return EventRead.model_validate(stored_event)


@router.get("", response_model=list[EventRead])
def get_events(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    source: Source | None = None,
    db: Session = Depends(get_db),
) -> list[EventRead]:
    events = list_events(
        db,
        limit=limit,
        offset=offset,
        source=source,
    )

    return [EventRead.model_validate(event) for event in events]


@router.delete("/{event_id}", response_model=DeletionResult)
def delete_single_event(
    event_id: UUID,
    db: Session = Depends(get_db),
) -> DeletionResult:
    deleted_count = delete_event_by_id(db, str(event_id))

    if deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found.",
        )

    return DeletionResult(
        deleted_count=deleted_count,
        scope="single_event",
        audit_action="raw_event_deleted",
    )


@router.delete("", response_model=DeletionResult)
def delete_filtered_events(
    source: Source | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> DeletionResult:
    try:
        deleted_count = delete_events_by_filter(
            db,
            source=source,
            from_time=from_time,
            to_time=to_time,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return DeletionResult(
        deleted_count=deleted_count,
        scope="filtered_events",
        audit_action="raw_events_deleted_by_filter",
    )
