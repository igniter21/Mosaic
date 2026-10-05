"""Context reconstruction, sessionization and context-aware retrieval."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.context_models import (
    ActivitySession,
    Goal,
    GoalMemory,
    Project,
    ProjectMemory,
    SessionEvent,
)
from mosaic_memory_api.db.models import (
    DerivedMemory,
    MemoryEmbedding,
    MemoryEvidence,
    RawEvent,
)
from mosaic_memory_api.domain.context import SessionDetailRead, SessionRead
from mosaic_memory_api.domain.events import EventRead, Source
from mosaic_memory_api.services.memory_service import (
    evidence_for_memory,
    links_for_memory,
    normalized_terms,
    query_time_window,
    rank_memories,
)
from mosaic_memory_api.services.semantic_index import (
    semantic_candidate_scores,
)

SESSION_GAP = timedelta(minutes=30)
PROJECT_KEYS = ("repo_name", "repository", "git_remote", "workspace_name", "project")


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or f"project-{uuid4().hex[:8]}"


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def project_key_for_event(event: RawEvent) -> str:
    for key in PROJECT_KEYS:
        value = event.payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if event.source == Source.VSCODE.value:
        value = event.payload.get("workspace_name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    if event.source == Source.GIT.value:
        value = event.payload.get("repository_name")
        if isinstance(value, str) and value.strip():
            return value.strip()
    host = event.payload.get("host")
    if (
        isinstance(host, str)
        and host.strip()
        and event.source in {Source.BROWSER.value, Source.YOUTUBE.value}
    ):
        return host.strip()
    return "Unassigned"


def get_or_create_project(
    db: Session, key: str, event: RawEvent | None = None
) -> Project:
    slug = _slug(key)
    project = db.scalar(select(Project).where(Project.slug == slug))
    now = _as_utc(event.occurred_at if event is not None else datetime.now(UTC))
    if project is None:
        project = Project(
            name=key[:200],
            slug=slug,
            repository=_first_string(event, ("repository", "git_remote", "repo_name"))
            if event
            else None,
            workspace_name=_first_string(event, ("workspace_name",)) if event else None,
            last_seen_at=now,
        )
        db.add(project)
        db.flush()
    else:
        project.last_seen_at = max(_as_utc(project.last_seen_at), now)
        if event is not None:
            project.repository = project.repository or _first_string(
                event, ("repository", "git_remote", "repo_name")
            )
            project.workspace_name = project.workspace_name or _first_string(
                event, ("workspace_name",)
            )
    return project


def _first_string(event: RawEvent | None, keys: tuple[str, ...]) -> str | None:
    if event is None:
        return None
    for key in keys:
        value = event.payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:500]
    return None


def _session_summary(
    events: list[RawEvent],
) -> str:
    titles = [
        event.title
        or event.event_type.replace("_", " ")
        for event in events
        if event.title or event.event_type
    ]

    sources = list(
        dict.fromkeys(
            event.source
            for event in events
        )
    )

    stop_words = {
        "the",
        "and",
        "with",
        "from",
        "this",
        "that",
        "into",
        "your",
        "have",
        "was",
        "were",
        "open",
        "opened",
        "page",
        "file",
        "document",
        "browser",
        "youtube",
        "vscode",
        "leetcode",
    }

    terms = Counter()

    for event in events:
        raw_text = " ".join(
            [
                event.title or "",
                str(
                    event.payload.get(
                        "description",
                        "",
                    )
                ),
            ]
        )

        for token in re.findall(
            r"[a-zA-Z][a-zA-Z0-9_-]{2,}",
            raw_text.lower(),
        ):
            if token in stop_words:
                continue

            terms[token] += 1

        context_topics = event.payload.get(
            "context_topics"
        )

        if isinstance(
            context_topics,
            list,
        ):
            for topic in context_topics:
                if not isinstance(
                    topic,
                    str,
                ):
                    continue

                cleaned = topic.strip().lower()

                if (
                    cleaned
                    and cleaned not in stop_words
                ):
                    terms[cleaned] += 2

    topics = [
        topic
        for topic, _ in terms.most_common(5)
    ]

    source_text = ", ".join(
        sources
    )

    if topics:
        return (
            f"{source_text}: "
            f"{', '.join(topics)}"
        )[:1000]

    fallback_titles = list(
        dict.fromkeys(titles)
    )[:4]

    return (
        f"{source_text}: "
        f"{'; '.join(fallback_titles)}"
    )[:1000]


def _focus_score(events: list[RawEvent]) -> float:
    if not events:
        return 0.0
    source_switches = sum(
        1 for left, right in pairwise(events) if left.source != right.source
    )
    intervals = [
        (_as_utc(later.occurred_at) - _as_utc(earlier.occurred_at)).total_seconds() / 60
        for earlier, later in pairwise(events)
    ]
    if not intervals:
        return 0.5
    within_15m = sum(1 for value in intervals if value <= 15) / len(intervals)
    switch_penalty = min(source_switches / max(len(events) - 1, 1), 1.0)
    return round(max(0.0, min(1.0, 0.65 * within_15m + 0.35 * (1 - switch_penalty))), 3)


def rebuild_sessions(db: Session) -> int:
    db.execute(delete(SessionEvent))
    db.execute(delete(ActivitySession))
    db.execute(delete(ProjectMemory))
    db.execute(delete(GoalMemory))
    events = list(
        db.scalars(select(RawEvent).order_by(RawEvent.occurred_at.asc())).all()
    )
    groups: list[list[RawEvent]] = []
    current: list[RawEvent] = []
    current_key: str | None = None

    for event in events:
        key = project_key_for_event(event)
        if not current:
            current = [event]
            current_key = key
            continue
        gap = _as_utc(event.occurred_at) - _as_utc(current[-1].occurred_at)
        if gap > SESSION_GAP or key != current_key:
            groups.append(current)
            current = [event]
            current_key = key
        else:
            current.append(event)
    if current:
        groups.append(current)

    for group in groups:
        project = get_or_create_project(db, project_key_for_event(group[0]), group[-1])
        session = ActivitySession(
            started_at=_as_utc(group[0].occurred_at),
            ended_at=_as_utc(group[-1].occurred_at),
            project_id=project.id,
            summary=_session_summary(group),
            source_count=len({event.source for event in group}),
            event_count=len(group),
            focus_score=_focus_score(group),
            goal_hint=_goal_hint(group),
            metadata_json={
                "source_sequence": list(dict.fromkeys(event.source for event in group))
            },
        )
        db.add(session)
        db.flush()
        for event in group:
            db.add(SessionEvent(session_id=session.id, event_id=event.id))
            memory = db.scalar(
                select(DerivedMemory)
                .join(MemoryEvidence, MemoryEvidence.memory_id == DerivedMemory.id)
                .where(MemoryEvidence.event_id == event.id)
            )
            if memory is not None:
                _associate_memory_to_project(db, project, memory)
                _associate_memory_to_goals(db, project, memory)
    db.commit()
    return len(groups)


def _associate_memory_to_project(
    db: Session, project: Project, memory: DerivedMemory
) -> None:
    if (
        db.scalar(
            select(ProjectMemory.id).where(
                ProjectMemory.project_id == project.id,
                ProjectMemory.memory_id == memory.id,
            )
        )
        is None
    ):
        db.add(ProjectMemory(project_id=project.id, memory_id=memory.id))


def _associate_memory_to_goals(
    db: Session, project: Project, memory: DerivedMemory
) -> None:
    active_goals = list(db.scalars(select(Goal).where(Goal.status == "active")).all())
    memory_terms = set(memory.keywords)
    for goal in active_goals:
        if goal.project_id and goal.project_id != project.id:
            continue
        goal_terms = set(
            re.findall(r"[a-z0-9]+", f"{goal.title} {goal.description}".lower())
        )
        overlap = len(memory_terms.intersection(goal_terms))
        if overlap <= 0:
            continue
        confidence = min(1.0, 0.4 + 0.15 * overlap)
        existing = db.scalar(
            select(GoalMemory.id).where(
                GoalMemory.goal_id == goal.id, GoalMemory.memory_id == memory.id
            )
        )
        if existing is None:
            db.add(
                GoalMemory(goal_id=goal.id, memory_id=memory.id, confidence=confidence)
            )


def _goal_hint(events: list[RawEvent]) -> str | None:
    terms = Counter()
    for event in events:
        raw = f"{event.title or ''} {event.payload.get('description', '')}"
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", raw.lower()):
            if token not in {
                "the",
                "and",
                "with",
                "from",
                "this",
                "that",
                "file",
                "page",
            }:
                terms[token] += 1
    if not terms:
        return None
    return "Investigate " + ", ".join(token for token, _ in terms.most_common(3))


def list_sessions(db: Session, limit: int = 20) -> list[SessionRead]:
    sessions = list(
        db.scalars(
            select(ActivitySession)
            .order_by(ActivitySession.started_at.desc())
            .limit(limit)
        ).all()
    )
    output: list[SessionRead] = []
    for session in sessions:
        event_ids = list(
            db.scalars(
                select(SessionEvent.event_id).where(
                    SessionEvent.session_id == session.id
                )
            ).all()
        )
        output.append(
            SessionRead(
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
            )
        )
    return output


def _recency_boost(occurred_at: datetime, now: datetime) -> float:
    age_hours = max(0.0, (_as_utc(now) - _as_utc(occurred_at)).total_seconds() / 3600)
    return 0.12 * math.exp(-age_hours / 72.0)


def _infer_task_intent(query: str) -> dict[str, Any]:
    lowered = query.lower()
    intents: dict[str, Any] = {
        "resume": False,
        "learning": False,
        "code": False,
        "research": False,
        "source_boosts": {},
    }
    if any(
        term in lowered
        for term in (
            "resume",
            "continue",
            "where did i leave",
            "pick up",
            "last worked",
        )
    ):
        intents["resume"] = True
    if any(
        term in lowered
        for term in ("learn", "study", "practice", "leetcode", "understand")
    ):
        intents["learning"] = True
        intents["source_boosts"] = {
            Source.LEETCODE.value: 0.08,
            Source.YOUTUBE.value: 0.05,
            Source.DOCUMENT.value: 0.05,
        }
    if any(
        term in lowered
        for term in (
            "code",
            "coding",
            "debug",
            "implement",
            "repository",
            "git",
            "vscode",
        )
    ):
        intents["code"] = True
        intents["source_boosts"] = {
            **intents["source_boosts"],
            Source.VSCODE.value: 0.08,
            Source.GIT.value: 0.05,
        }
    if any(
        term in lowered for term in ("research", "read", "compare", "paper", "article")
    ):
        intents["research"] = True
        intents["source_boosts"] = {
            **intents["source_boosts"],
            Source.BROWSER.value: 0.06,
            Source.DOCUMENT.value: 0.06,
            Source.YOUTUBE.value: 0.03,
        }
    return intents


def _policy_allows(
    event: RawEvent,
    allowed_sources: set[str],
    denied_sources: set[str],
    deny_sensitive: bool,
) -> bool:
    if allowed_sources and event.source not in allowed_sources:
        return False
    if event.source in denied_sources:
        return False
    return not (deny_sensitive and event.privacy_level == "sensitive")


def context_search(
    db: Session,
    *,
    query: str,
    limit: int,
    project_id: str | None = None,
    goal_id: str | None = None,
    source: Source | None = None,
    allowed_sources: set[str] | None = None,
    denied_sources: set[str] | None = None,
    deny_sensitive: bool = True,
    allowed_projects: set[str] | None = None,
) -> tuple[list[tuple[DerivedMemory, float]], dict[str, Any]]:
    now = datetime.now(UTC)
    intent = _infer_task_intent(query)
    lexical_candidates = rank_memories(
        db,
        query=query,
        limit=max(40, limit * 5),
        now=now,
    )

    base_scores = {
        memory.id: score
        for memory, score in lexical_candidates
    }

    allowed_sources = allowed_sources or set()
    denied_sources = denied_sources or set()

    project_memory_ids: set[str] = set()
    if project_id:
        project_memory_ids = set(
            db.scalars(
                select(ProjectMemory.memory_id).where(
                    ProjectMemory.project_id == project_id
                )
            ).all()
        )
    allowed_project_memory_ids: set[str] | None = None
    if allowed_projects:
        allowed_project_memory_ids = set(
            db.scalars(
                select(ProjectMemory.memory_id).where(
                    ProjectMemory.project_id.in_(allowed_projects)
                )
            ).all()
        )
    goal_memory_ids: set[str] = set()
    if goal_id:
        goal_memory_ids = set(
            db.scalars(
                select(GoalMemory.memory_id).where(GoalMemory.goal_id == goal_id)
            ).all()
        )

    semantic_by_id = semantic_candidate_scores(
        db,
        query,
        limit=max(80, limit * 10),
    )

    time_window = query_time_window(
        query,
        now,
    )

    # For pure date questions such as "today", "yesterday",
    # semantic similarity should not override the date filter.
    if (
        time_window is not None
        and not normalized_terms(query)
    ):
        semantic_by_id = {}

    candidate_ids = list(
        dict.fromkeys(
            [
                memory.id
                for memory, _ in lexical_candidates
            ]
            + list(semantic_by_id.keys())
        )
    )

    candidate_memories = list(
        db.scalars(
            select(DerivedMemory).where(
                DerivedMemory.id.in_(candidate_ids)
            )
        ).all()
    )

    reranked: list[tuple[DerivedMemory, float]] = []
    filtered = 0
    for memory in candidate_memories:
        base_score = base_scores.get(memory.id, 0.0)
        if time_window is not None:
            occurred_at = _as_utc(
                memory.occurred_at
            )
            if not (
                time_window[0]
                <= occurred_at
                < time_window[1]
            ):
                continue
        evidence = evidence_for_memory(db, memory.id)
        if not evidence:
            filtered += 1
            continue
        if any(
            not _policy_allows(
                item.event, allowed_sources, denied_sources, deny_sensitive
            )
            for item in evidence
        ):
            filtered += 1
            continue
        if (
            allowed_project_memory_ids is not None
            and memory.id not in allowed_project_memory_ids
        ):
            filtered += 1
            continue
        if source is not None and memory.source != source.value:
            continue
        semantic_score = semantic_by_id.get(memory.id, 0.0)
        score = (
            (0.55 * base_score)
            + (0.25 * semantic_score)
            + _recency_boost(memory.occurred_at, now)
        )
        if project_id and memory.id in project_memory_ids:
            score += 0.20
        if goal_id and memory.id in goal_memory_ids:
            score += 0.20
        score += intent["source_boosts"].get(memory.source, 0.0)
        if score > 0:
            reranked.append(
                (
                    memory,
                    min(1.0, score),
                )
            )

    reranked.sort(
        key=lambda item: (item[1], _as_utc(item[0].occurred_at)), reverse=True
    )

    receipt = {
        "candidate_count": len(candidate_ids),
        "filtered_count": filtered,
        "project_boost": bool(project_id),
        "goal_boost": bool(goal_id),
        "recency_boost": True,
        "semantic_rerank": bool(semantic_by_id),
        "semantic_retrieval": bool(semantic_by_id),
        "policy_filtered": True,
        "allowed_project_count": len(allowed_projects or set()),
        "task_intent": {
            key: value for key, value in intent.items() if key != "source_boosts"
        },
        "source_intent_boosts": intent["source_boosts"],
    }
    return reranked[:limit], receipt


def serialize_memory(
    db: Session, memory: DerivedMemory, score: float
) -> dict[str, Any]:
    embedding = db.get(MemoryEmbedding, memory.id)
    evidence = evidence_for_memory(db, memory.id)
    links = links_for_memory(db, memory.id)
    return {
        "id": memory.id,
        "occurred_at": memory.occurred_at,
        "source": memory.source,
        "summary": memory.summary,
        "keywords": memory.keywords,
        "model_id": embedding.model if embedding else "unknown",
        "score": round(score, 4),
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "links": [item.model_dump(mode="json") for item in links],
    }


def current_session(db: Session) -> SessionRead | None:
    session = db.scalar(
        select(ActivitySession).order_by(ActivitySession.started_at.desc()).limit(1)
    )
    if session is None:
        return None
    ids = list(
        db.scalars(
            select(SessionEvent.event_id).where(SessionEvent.session_id == session.id)
        ).all()
    )
    return SessionRead(
        id=session.id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        project_id=session.project_id,
        summary=session.summary,
        source_count=session.source_count,
        event_count=session.event_count,
        focus_score=session.focus_score,
        goal_hint=session.goal_hint,
        event_ids=ids,
    )


def sync_incremental_context(
    db: Session, event: RawEvent, memory: DerivedMemory
) -> None:
    """Update project/session/goal links for one newly ingested event."""
    project = get_or_create_project(db, project_key_for_event(event), event)
    _associate_memory_to_project(db, project, memory)

    latest = db.scalar(
        select(ActivitySession).order_by(ActivitySession.ended_at.desc()).limit(1)
    )
    event_occurred = _as_utc(event.occurred_at)
    latest_ended = _as_utc(latest.ended_at) if latest and latest.ended_at else None
    should_join = bool(
        latest
        and latest.project_id == project.id
        and latest_ended is not None
        and event_occurred - latest_ended <= SESSION_GAP
        and event_occurred >= latest_ended
    )
    if should_join and latest is not None and latest_ended is not None:
        latest.ended_at = max(latest_ended, event_occurred)
        latest.event_count += 1
        latest.source_count = len(
            set(
                db.scalars(
                    select(RawEvent.source)
                    .join(SessionEvent, SessionEvent.event_id == RawEvent.id)
                    .where(SessionEvent.session_id == latest.id)
                ).all()
            )
        )
        latest.focus_score = min(1.0, latest.focus_score + 0.02)
        latest.summary = _session_summary(
            list(
                db.scalars(
                    select(RawEvent)
                    .join(SessionEvent, SessionEvent.event_id == RawEvent.id)
                    .where(SessionEvent.session_id == latest.id)
                    .order_by(RawEvent.occurred_at.asc())
                ).all()
            )
            + [event]
        )
    else:
        latest = ActivitySession(
            started_at=event_occurred,
            ended_at=event_occurred,
            project_id=project.id,
            summary=_session_summary([event]),
            source_count=1,
            event_count=1,
            focus_score=0.5,
            goal_hint=_goal_hint([event]),
        )
        db.add(latest)
        db.flush()
    if (
        db.scalar(
            select(SessionEvent.id).where(
                SessionEvent.session_id == latest.id, SessionEvent.event_id == event.id
            )
        )
        is None
    ):
        db.add(SessionEvent(session_id=latest.id, event_id=event.id))

    _associate_memory_to_goals(db, project, memory)
    db.flush()


def session_detail(db: Session, session_id: str) -> SessionDetailRead | None:
    session = db.get(ActivitySession, session_id)
    if session is None:
        return None
    events = list(
        db.scalars(
            select(RawEvent)
            .join(SessionEvent, SessionEvent.event_id == RawEvent.id)
            .where(SessionEvent.session_id == session.id)
            .order_by(RawEvent.occurred_at.asc())
        ).all()
    )
    return SessionDetailRead(
        id=session.id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        project_id=session.project_id,
        summary=session.summary,
        source_count=session.source_count,
        event_count=session.event_count,
        focus_score=session.focus_score,
        goal_hint=session.goal_hint,
        event_ids=[event.id for event in events],
        events=[EventRead.model_validate(event) for event in events],
    )
