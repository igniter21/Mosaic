from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.context_models import MemoryLifecycle
from mosaic_memory_api.db.models import (
    DerivedMemory,
    MemoryEmbedding,
    MemoryEvidence,
    MemoryLink,
    RawEvent,
)
from mosaic_memory_api.domain.context import LifecyclePreview, LifecycleRunResult

RETENTION_AGE = {
    "temporary": timedelta(days=1),
    "short_term": timedelta(days=30),
}


def sync_lifecycle_states(db: Session) -> None:
    memories = list(db.scalars(select(DerivedMemory)).all())
    for memory in memories:
        state = db.get(MemoryLifecycle, memory.id)
        if state is not None:
            continue
        event = db.scalar(
            select(RawEvent)
            .join(MemoryEvidence, MemoryEvidence.event_id == RawEvent.id)
            .where(MemoryEvidence.memory_id == memory.id)
        )
        age = RETENTION_AGE.get(event.retention_class) if event else None
        db.add(
            MemoryLifecycle(
                memory_id=memory.id,
                importance=0.5,
                expires_at=(memory.occurred_at + age) if age else None,
                reason="retention_class",
            )
        )
    db.commit()


def preview_lifecycle(db: Session) -> LifecyclePreview:
    sync_lifecycle_states(db)
    now = datetime.now(UTC)
    states = list(db.scalars(select(MemoryLifecycle)).all())
    expired = [
        state.memory_id
        for state in states
        if state.expires_at and state.expires_at <= now and not state.pinned
    ]
    temp_count = 0
    short_count = 0
    for state in states:
        if state.memory_id in expired:
            memory = db.get(DerivedMemory, state.memory_id)
            if memory is not None:
                event = db.scalar(
                    select(RawEvent)
                    .join(MemoryEvidence, MemoryEvidence.event_id == RawEvent.id)
                    .where(MemoryEvidence.memory_id == memory.id)
                )
                if event and event.retention_class == "temporary":
                    temp_count += 1
                elif event:
                    short_count += 1
    protected = sum(1 for state in states if state.pinned)
    return LifecyclePreview(
        expired_memory_ids=expired,
        temporary_candidates=temp_count,
        short_term_candidates=short_count,
        protected_pinned=protected,
    )


def run_lifecycle(db: Session, execute: bool) -> LifecycleRunResult:
    preview = preview_lifecycle(db)
    if not execute:
        return LifecycleRunResult(
            deleted_memory_count=0, deleted_event_count=0, dry_run=True
        )
    memory_ids = preview.expired_memory_ids
    if not memory_ids:
        return LifecycleRunResult(
            deleted_memory_count=0, deleted_event_count=0, dry_run=False
        )
    event_ids = list(
        db.scalars(
            select(MemoryEvidence.event_id).where(
                MemoryEvidence.memory_id.in_(memory_ids)
            )
        ).all()
    )
    db.execute(delete(MemoryLifecycle).where(MemoryLifecycle.memory_id.in_(memory_ids)))
    db.execute(
        delete(MemoryLink).where(
            MemoryLink.source_memory_id.in_(memory_ids)
            | MemoryLink.target_memory_id.in_(memory_ids)
        )
    )
    db.execute(delete(MemoryEmbedding).where(MemoryEmbedding.memory_id.in_(memory_ids)))
    db.execute(delete(MemoryEvidence).where(MemoryEvidence.memory_id.in_(memory_ids)))
    db.execute(delete(DerivedMemory).where(DerivedMemory.id.in_(memory_ids)))
    if event_ids:
        db.execute(delete(RawEvent).where(RawEvent.id.in_(event_ids)))
    db.commit()
    return LifecycleRunResult(
        deleted_memory_count=len(memory_ids),
        deleted_event_count=len(event_ids),
        dry_run=False,
    )
