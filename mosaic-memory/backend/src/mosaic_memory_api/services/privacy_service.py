from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from mosaic_memory_api.db.models import (
    AuditLog,
    DerivedMemory,
    MemoryEmbedding,
    MemoryLink,
    RawEvent,
    SourceSetting,
)
from mosaic_memory_api.db.session import engine
from mosaic_memory_api.domain.events import Source
from mosaic_memory_api.domain.privacy import GlobalEraseResult
from mosaic_memory_api.services.memory_service import (
    delete_all_derived_memory_data,
    delete_derived_memories_for_events,
)

ERASE_ALL_CONFIRMATION = "ERASE ALL LOCAL MEMORY"


class SourceDisabledError(Exception):
    pass


class InvalidGlobalEraseConfirmationError(Exception):
    pass


def get_or_create_source_setting(
    db: Session,
    source: Source,
) -> SourceSetting:
    setting = db.get(SourceSetting, source.value)

    if setting is None:
        setting = SourceSetting(source=source.value, enabled=False)
        db.add(setting)
        db.flush()

    return setting


def list_source_settings(db: Session) -> list[SourceSetting]:
    for source in Source:
        get_or_create_source_setting(db, source)

    db.commit()

    statement = select(SourceSetting).order_by(SourceSetting.source)
    return list(db.scalars(statement).all())


def set_source_enabled(
    db: Session,
    source: Source,
    enabled: bool,
) -> SourceSetting:
    setting = get_or_create_source_setting(db, source)
    setting.enabled = enabled

    db.commit()
    db.refresh(setting)

    return setting


def source_is_enabled(db: Session, source: Source) -> bool:
    setting = get_or_create_source_setting(db, source)
    return setting.enabled


def delete_event_by_id(db: Session, event_id: str) -> int:
    event = db.get(RawEvent, event_id)

    if event is None:
        return 0

    delete_derived_memories_for_events(db, [event.id])
    db.delete(event)

    db.add(
        AuditLog(
            action="raw_event_deleted",
            source=event.source,
            deleted_count=1,
        )
    )

    db.commit()
    return 1


def delete_events_by_filter(
    db: Session,
    *,
    source: Source | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> int:
    if source is None and from_time is None and to_time is None:
        raise ValueError("Choose a source, a date range, or both.")

    if from_time and to_time and from_time > to_time:
        raise ValueError("'from' must be before 'to'.")

    statement = select(RawEvent)

    if source:
        statement = statement.where(RawEvent.source == source.value)

    if from_time:
        statement = statement.where(RawEvent.occurred_at >= from_time)

    if to_time:
        statement = statement.where(RawEvent.occurred_at <= to_time)

    events = list(db.scalars(statement).all())
    delete_derived_memories_for_events(db, [event.id for event in events])

    for event in events:
        db.delete(event)

    db.add(
        AuditLog(
            action="raw_events_deleted_by_filter",
            source=source.value if source else None,
            deleted_count=len(events),
        )
    )

    db.commit()
    return len(events)


def erase_all_local_memory(
    db: Session,
    confirmation: str,
) -> GlobalEraseResult:
    if confirmation.strip() != ERASE_ALL_CONFIRMATION:
        raise InvalidGlobalEraseConfirmationError(
            "The confirmation phrase is incorrect."
        )

    raw_events_deleted = int(
        db.scalar(select(func.count()).select_from(RawEvent)) or 0
    )
    derived_memories_deleted = int(
        db.scalar(select(func.count()).select_from(DerivedMemory)) or 0
    )
    embeddings_deleted = int(
        db.scalar(select(func.count()).select_from(MemoryEmbedding)) or 0
    )
    graph_links_deleted = int(
        db.scalar(select(func.count()).select_from(MemoryLink)) or 0
    )
    audit_logs_deleted = int(
        db.scalar(select(func.count()).select_from(AuditLog)) or 0
    )

    sources_disabled = 0

    for source in Source:
        setting = get_or_create_source_setting(db, source)

        if setting.enabled:
            sources_disabled += 1

        setting.enabled = False

    delete_all_derived_memory_data(db)
    db.execute(delete(RawEvent))
    db.execute(delete(AuditLog))
    db.commit()

    vacuum_performed = vacuum_database()

    return GlobalEraseResult(
        raw_events_deleted=raw_events_deleted,
        derived_memories_deleted=derived_memories_deleted,
        embeddings_deleted=embeddings_deleted,
        graph_links_deleted=graph_links_deleted,
        audit_logs_deleted=audit_logs_deleted,
        sources_disabled=sources_disabled,
        vacuum_performed=vacuum_performed,
    )


def vacuum_database() -> bool:
    try:
        with engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.exec_driver_sql("VACUUM")

        return True
    except SQLAlchemyError:
        return False
