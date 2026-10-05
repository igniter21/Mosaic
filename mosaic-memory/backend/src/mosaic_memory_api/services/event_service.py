"""Event ingestion with deduplication.

When the same URL or activity is seen multiple times in a short window,
the system bumps the existing row's ``visit_count`` and updates
``occurred_at`` to the latest timestamp, keeping ``first_seen_at``
unchanged.  This prevents the timeline from being cluttered with
back-to-back duplicate entries (e.g. refreshing the same page) while
preserving accurate visit-frequency metadata.
"""

from datetime import timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session
from mosaic_memory_api.services.semantic_index import (
    ensure_semantic_embedding,
)

from mosaic_memory_api.db.models import RawEvent
from mosaic_memory_api.domain.events import EventCreate, Source
from mosaic_memory_api.services.context_engine import sync_incremental_context
from mosaic_memory_api.services.domain_policy_service import enforce_domain_policy
from mosaic_memory_api.services.memory_service import build_memory_for_event
from mosaic_memory_api.services.privacy_service import (
    SourceDisabledError,
    source_is_enabled,
)

# Events with the same fingerprint within this window are coalesced.
DEDUP_WINDOW = timedelta(minutes=5)


def _dedup_fingerprint(event: EventCreate) -> tuple[str, ...]:
    """Build a tuple that uniquely identifies *repeated* activity.

    For browser events the fingerprint is (source, host, path).
    For everything else it is (source, event_type, title).
    """
    source = event.source.value
    if event.source in (Source.BROWSER, Source.YOUTUBE, Source.DOCUMENT):
        host = str(event.payload.get("host", "")) if isinstance(event.payload, dict) else ""
        path = str(event.payload.get("path", "")) if isinstance(event.payload, dict) else ""
        return (source, host, path)

    return (source, event.event_type, event.title or "")


def _find_recent_duplicate(
    db: Session,
    event: EventCreate,
    *,
    window: timedelta = DEDUP_WINDOW,
) -> RawEvent | None:
    """Find an existing event that matches the same fingerprint within *window*."""
    fingerprint = _dedup_fingerprint(event)
    cutoff = event.occurred_at - window

    if event.source in (Source.BROWSER, Source.YOUTUBE, Source.DOCUMENT):
        # Match on source + payload host + path
        source_val, host, path = fingerprint
        stmt = (
            select(RawEvent)
            .where(
                and_(
                    RawEvent.source == source_val,
                    RawEvent.occurred_at >= cutoff,
                )
            )
            .order_by(RawEvent.occurred_at.desc())
            .limit(20)
        )
        for row in db.scalars(stmt).all():
            row_host = str(row.payload.get("host", "")) if isinstance(row.payload, dict) else ""
            row_path = str(row.payload.get("path", "")) if isinstance(row.payload, dict) else ""
            if row_host == host and row_path == path:
                return row
    else:
        source_val, event_type, title = fingerprint
        stmt = (
            select(RawEvent)
            .where(
                and_(
                    RawEvent.source == source_val,
                    RawEvent.event_type == event_type,
                    RawEvent.occurred_at >= cutoff,
                )
            )
            .order_by(RawEvent.occurred_at.desc())
            .limit(20)
        )
        for row in db.scalars(stmt).all():
            if (row.title or "") == title:
                return row

    return None


def create_event(db: Session, event: EventCreate) -> RawEvent:
    if not source_is_enabled(db, event.source):
        raise SourceDisabledError(
            f"The {event.source.value} source is currently disabled."
        )
    host = event.payload.get("host") if isinstance(event.payload, dict) else None
    enforce_domain_policy(db, event.source, host if isinstance(host, str) else None)

    # Exact-ID idempotency guard (extension re-sends)
    existing_event = db.get(RawEvent, str(event.event_id))
    if existing_event:
        memory = build_memory_for_event(
            db,
            existing_event,
        )

        ensure_semantic_embedding(
            db,
            memory,
        )

        sync_incremental_context(
            db,
            existing_event,
            memory,
        )

        db.commit()
        return existing_event

    # ── Deduplication: coalesce into a recent identical entry ─────────
    duplicate = _find_recent_duplicate(db, event)
    if duplicate is not None:
        if duplicate.first_seen_at is None:
            duplicate.first_seen_at = duplicate.occurred_at
        duplicate.occurred_at = event.occurred_at
        duplicate.visit_count = (duplicate.visit_count or 1) + 1
        db.flush()
        memory = build_memory_for_event(
            db,
            duplicate,
        )

        ensure_semantic_embedding(
            db,
            memory,
        )

        sync_incremental_context(
            db,
            duplicate,
            memory,
        )
        db.commit()
        return duplicate

    # ── Brand-new event ──────────────────────────────────────────────
    raw_event = RawEvent(
        id=str(event.event_id),
        occurred_at=event.occurred_at,
        source=event.source.value,
        event_type=event.event_type,
        title=event.title,
        payload=event.payload,
        privacy_level=event.privacy_level.value,
        retention_class=event.retention_class.value,
        visit_count=1,
        first_seen_at=event.occurred_at,
    )
    db.add(raw_event)
    db.flush()
    memory = build_memory_for_event(
        db,
        raw_event,
    )

    ensure_semantic_embedding(
        db,
        memory,
    )

    sync_incremental_context(
        db,
        raw_event,
        memory,
    )
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
        statement.order_by(RawEvent.occurred_at.desc()).offset(offset).limit(limit)
    )
    return list(db.scalars(statement).all())
