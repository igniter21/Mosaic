from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.context_models import (
    ActivitySession,
    Goal,
    Project,
    SessionEvent,
)
from mosaic_memory_api.db.models import (
    DerivedMemory,
    MemoryEvidence,
    RawEvent,
)
from mosaic_memory_api.domain.context import (
    GoalRead,
    ProjectRead,
    ResumeContextRead,
    SessionRead,
)
from mosaic_memory_api.domain.context import (
    GoalRead,
    ProjectRead,
    ResumeContextRead,
)
from mosaic_memory_api.services.context_engine import (
    _policy_allows,
    evidence_for_memory,
    serialize_memory,
)
from mosaic_memory_api.services.policy_service import (
    get_policy,
)


def build_resume_context(
    db: Session,
    *,
    agent_name: str = "default",
    limit: int = 8,
) -> ResumeContextRead:
    now = datetime.now(UTC)

    session = db.scalar(
        select(ActivitySession)
        .order_by(
            ActivitySession.started_at.desc()
        )
        .limit(1)
    )

    if session is None:
        return ResumeContextRead(
            title="Nothing to resume yet",
            summary=(
                "Mosaic has not reconstructed a "
                "work session yet."
            ),
            generated_at=now,
            evidence_receipt={
                "session_found": False,
                "memories_included": 0,
            },
        )

    project = None

    if session.project_id:
        project = db.get(
            Project,
            session.project_id,
        )

    event_ids = list(
        db.scalars(
            select(SessionEvent.event_id).where(
                SessionEvent.session_id
                == session.id
            )
        ).all()
    )

    policy = get_policy(
        db,
        agent_name,
    )

    memories = list(
        db.scalars(
            select(DerivedMemory)
            .join(
                MemoryEvidence,
                MemoryEvidence.memory_id
                == DerivedMemory.id,
            )
            .where(
                MemoryEvidence.event_id.in_(
                    event_ids
                )
            )
            .order_by(
                DerivedMemory.occurred_at.desc()
            )
            .limit(limit * 2)
        ).all()
    )

    allowed_memories = []

    filtered_count = 0

    for memory in memories:
        evidence = evidence_for_memory(
            db,
            memory.id,
        )

        if not evidence:
            continue

        blocked = any(
            not _policy_allows(
                item.event,
                set(policy.allowed_sources),
                set(policy.denied_sources),
                policy.deny_sensitive,
            )
            for item in evidence
        )

        if blocked:
            filtered_count += 1
            continue

        allowed_memories.append(memory)

        if len(allowed_memories) >= limit:
            break

    goal_query = select(Goal).where(
        Goal.status != "completed",
        or_(
            Goal.project_id.is_(None),
            Goal.project_id == session.project_id,
        ),
    ).order_by(
        Goal.created_at.desc()
    ).limit(5)

    goals = list(
        db.scalars(goal_query).all()
    )

    events = list(
        db.scalars(
            select(RawEvent)
            .where(
                RawEvent.id.in_(event_ids)
            )
            .order_by(
                RawEvent.occurred_at.desc()
            )
        ).all()
    )

    sources = {
        event.source
        for event in events
    }

    steps: list[str] = []

    if (
        "vscode" in sources
        or "git" in sources
    ):
        steps.append(
            "Continue from the latest implementation "
            "and inspect the most recent code activity."
        )

    if (
        "browser" in sources
        or "youtube" in sources
        or "document" in sources
    ):
        steps.append(
            "Review the latest research evidence "
            "and turn the most useful finding into "
            "a concrete implementation or note."
        )

    if "leetcode" in sources:
        steps.append(
            "Continue the latest practice thread "
            "or record the algorithm pattern you were "
            "working on."
        )

    if session.goal_hint:
        steps.append(
            f"Validate the inferred thread: "
            f"{session.goal_hint}."
        )

    if goals:
        steps.append(
            f"Keep the active goal in focus: "
            f"{goals[0].title}."
        )

    if not steps:
        steps.append(
            "Review the most recent evidence and "
            "continue the latest activity thread."
        )

    project_read = (
        ProjectRead.model_validate(
            project,
            from_attributes=True,
        )
        if project is not None
        else None
    )

    goal_reads = [
        GoalRead.model_validate(
            goal,
            from_attributes=True,
        )
        for goal in goals
    ]

    serialized_memories = [
        serialize_memory(
            db,
            memory,
            1.0,
        )
        for memory in allowed_memories
    ]

    title = (
        f"Resume {project.name}"
        if project is not None
        else "Resume your latest work"
    )

    receipt = {
        "session_found": True,
        "session_id": session.id,
        "session_event_count": len(
            event_ids
        ),
        "memories_included": len(
            serialized_memories
        ),
        "policy_filtered": filtered_count,
        "agent": agent_name,
    }

    return ResumeContextRead(
        title=title,
        summary=session.summary,
        session=SessionRead(
    id=session.id,
    started_at=session.started_at,
    ended_at=session.ended_at,
    project_id=session.project_id,
    summary=session.summary,
    source_count=session.source_count,
    event_count=session.event_count,
    focus_score=session.focus_score,
    goal_hint=session.goal_hint,
    event_ids=event_ids,
),
        project=project_read,
        goals=goal_reads,
        memories=serialized_memories,
        suggested_next_steps=steps[:5],
        evidence_receipt=receipt,
        generated_at=now,
    )