"""Transparent, deterministic local memory derivation and retrieval.

This MVP deliberately avoids a hosted model.  It converts approved raw events
into short local summaries, stores a stable feature-hash vector, and ranks
queries using lexical overlap plus cosine similarity.  The API exposes raw
evidence for every result, so the user can verify what informed an answer.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.context_models import (
    GoalMemory,
    MemoryLifecycle,
    ProjectMemory,
)
from mosaic_memory_api.db.models import (
    DerivedMemory,
    MemoryEmbedding,
    MemoryEvidence,
    MemoryLink,
    RawEvent,
)
from mosaic_memory_api.db.semantic_models import SemanticEmbedding
from mosaic_memory_api.domain.events import EventRead, Source
from mosaic_memory_api.domain.memory import (
    AskMemoryResponse,
    DerivedMemoryRead,
    MemoryEvidenceRead,
    MemoryLinkRead,
)
from mosaic_memory_api.services.gemini_service import (
    GeminiRequestError,
    answer_tab_question,
)
from mosaic_memory_api.services.policy_service import record_privacy_action
from mosaic_memory_api.services.source_model_router import understand_event

EMBEDDING_DIMENSIONS = 192
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "about",
    "at",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "into",
    "is",
    "it",
    "last",
    "me",
    "my",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "with",
    "you",
    "activity",
    "browser",
    "document",
    "did",
    "do",
    "day",
    "days",
    "event",
    "indexed",
    "opened",
    "page",
    "past",
    "today",
    "viewed",
    "week",
    "weeks",
    "yesterday",
}
SEMANTIC_ROOTS = {
    "learn": {
        "learn",
        "learned",
        "learning",
        "study",
        "studied",
        "studying",
        "tutorial",
        "course",
        "lecture",
    },
    "code": {
        "code",
        "coding",
        "developer",
        "development",
        "program",
        "programming",
        "vscode",
        "github",
    },
    "practice": {
        "challenge",
        "exercise",
        "leetcode",
        "practice",
        "problem",
        "solve",
        "solved",
        "solving",
    },
    "research": {
        "browse",
        "browser",
        "read",
        "reading",
        "research",
        "search",
        "searched",
    },
    "watch": {"video", "view", "viewed", "watch", "watched", "youtube"},
    "write": {"document", "file", "save", "saved", "writing", "wrote"},
}
SEMANTIC_LOOKUP = {
    term: root for root, terms in SEMANTIC_ROOTS.items() for term in terms
}


def tokenize(value: str) -> list[str]:
    return TOKEN_PATTERN.findall(value.lower())


def normalized_terms(value: str) -> list[str]:
    terms: list[str] = []

    for token in tokenize(value):
        if token in STOP_WORDS or len(token) < 2:
            continue

        terms.append(token)
        root = SEMANTIC_LOOKUP.get(token)
        if root and root != token:
            terms.append(root)

    return terms


def keywords_for_text(value: str) -> list[str]:
    return list(dict.fromkeys(normalized_terms(value)))[:16]


def embed_terms(terms: Iterable[str]) -> list[float]:
    values = [0.0] * EMBEDDING_DIMENSIONS

    for term, count in Counter(terms).items():
        digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        values[bucket] += sign * float(count)

    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude == 0:
        return values

    return [value / magnitude for value in values]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left or not right:
        return 0.0

    return max(0.0, sum(a * b for a, b in zip(left, right, strict=True)))


def build_memory_for_event(db: Session, event: RawEvent) -> DerivedMemory:
    """Create one evidence-backed derived memory for an approved raw event."""
    understanding = understand_event(event)
    keywords = keywords_for_text(understanding.searchable_text)
    existing_memory_id = db.scalar(
        select(MemoryEvidence.memory_id).where(MemoryEvidence.event_id == event.id)
    )
    if existing_memory_id is not None:
        existing_memory = db.get(DerivedMemory, existing_memory_id)
        if existing_memory is not None:
            embedding = db.get(MemoryEmbedding, existing_memory.id)
            if embedding is None or embedding.model != understanding.model_id:
                existing_memory.summary = understanding.summary
                existing_memory.keywords = keywords
                if embedding is None:
                    db.add(
                        MemoryEmbedding(
                            memory_id=existing_memory.id,
                            model=understanding.model_id,
                            dimensions=EMBEDDING_DIMENSIONS,
                            vector=embed_terms(keywords),
                        )
                    )
                else:
                    embedding.model = understanding.model_id
                    embedding.dimensions = EMBEDDING_DIMENSIONS
                    embedding.vector = embed_terms(keywords)

                db.execute(
                    delete(MemoryLink).where(
                        or_(
                            MemoryLink.source_memory_id == existing_memory.id,
                            MemoryLink.target_memory_id == existing_memory.id,
                        )
                    )
                )
                db.flush()
                create_memory_links(db, existing_memory)
            return existing_memory

    memory = DerivedMemory(
        id=str(uuid4()),
        occurred_at=event.occurred_at,
        source=event.source,
        summary=understanding.summary,
        keywords=keywords,
    )
    db.add(memory)
    db.flush()

    db.add(MemoryEvidence(memory_id=memory.id, event_id=event.id))
    db.add(
        MemoryEmbedding(
            memory_id=memory.id,
            model=understanding.model_id,
            dimensions=EMBEDDING_DIMENSIONS,
            vector=embed_terms(keywords),
        )
    )
    create_memory_links(db, memory)
    return memory


def create_memory_links(db: Session, memory: DerivedMemory) -> None:
    memory_terms = set(memory.keywords)
    if not memory_terms:
        return

    previous_memories = db.scalars(
        select(DerivedMemory).where(DerivedMemory.id != memory.id)
    ).all()

    for previous in previous_memories:
        shared_keywords = sorted(memory_terms.intersection(previous.keywords))[:5]
        if not shared_keywords:
            continue

        db.add(
            MemoryLink(
                source_memory_id=memory.id,
                target_memory_id=previous.id,
                relation="shares_topic",
                shared_keywords=shared_keywords,
            )
        )


def ensure_memories_for_events(db: Session) -> None:
    events = db.scalars(select(RawEvent).order_by(RawEvent.occurred_at.desc())).all()
    for event in events:
        build_memory_for_event(db, event)
    db.commit()


def query_time_window(query: str, now: datetime) -> tuple[datetime, datetime] | None:
    lowered = query.lower()
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if "yesterday" in lowered:
        return start_of_today - timedelta(days=1), start_of_today
    if "today" in lowered:
        return start_of_today, now
    if (
        "last week" in lowered
        or "past week" in lowered
        or "last 7 days" in lowered
        or "past 7 days" in lowered
        or "last seven days" in lowered
        or "past seven days" in lowered
    ):
        return now - timedelta(days=7), now

    return None


def rank_memories(
    db: Session,
    *,
    query: str,
    limit: int,
    now: datetime,
) -> list[tuple[DerivedMemory, float]]:
    query_terms = normalized_terms(query)
    query_embedding = embed_terms(query_terms)
    time_window = query_time_window(query, now)
    statement = select(DerivedMemory).order_by(DerivedMemory.occurred_at.desc())

    if time_window is not None:
        statement = statement.where(
            DerivedMemory.occurred_at >= time_window[0],
            DerivedMemory.occurred_at < time_window[1],
        )

    ranked: list[tuple[DerivedMemory, float]] = []
    for memory in db.scalars(statement).all():
        memory_terms = set(memory.keywords)
        lexical_score = (
            len(memory_terms.intersection(query_terms)) / len(set(query_terms))
            if query_terms
            else 0.0
        )
        embedding = db.get(MemoryEmbedding, memory.id)
        vector_score = (
            cosine_similarity(query_embedding, embedding.vector)
            if embedding is not None
            else 0.0
        )
        score = (0.7 * lexical_score) + (0.3 * vector_score)

        # A date-only question should show the local activity in that time range.
        if time_window is not None and not query_terms:
            score = 0.1

        if score > 0:
            ranked.append((memory, min(score, 1.0)))

    ranked.sort(key=lambda item: (item[1], item[0].occurred_at), reverse=True)
    return ranked[:limit]


def evidence_for_memory(db: Session, memory_id: str) -> list[MemoryEvidenceRead]:
    event_ids = db.scalars(
        select(MemoryEvidence.event_id).where(MemoryEvidence.memory_id == memory_id)
    ).all()
    evidence: list[MemoryEvidenceRead] = []

    for event_id in event_ids:
        event = db.get(RawEvent, event_id)
        if event is not None:
            evidence.append(MemoryEvidenceRead(event=EventRead.model_validate(event)))

    return evidence


def links_for_memory(db: Session, memory_id: str) -> list[MemoryLinkRead]:
    links = db.scalars(
        select(MemoryLink).where(
            or_(
                MemoryLink.source_memory_id == memory_id,
                MemoryLink.target_memory_id == memory_id,
            )
        )
    ).all()
    return [
        MemoryLinkRead(
            memory_id=(
                link.target_memory_id
                if link.source_memory_id == memory_id
                else link.source_memory_id
            ),
            relation=link.relation,
            shared_keywords=link.shared_keywords,
        )
        for link in links[:8]
    ]


def answer_for_memories(query: str, memories: list[DerivedMemoryRead]) -> str:
    if not memories:
        return (
            f"I could not find a strong local match for “{query}”. "
            "Try a source name, a title, or a simpler topic."
        )

    sources = list(dict.fromkeys(memory.source.value for memory in memories))
    source_phrase = ", ".join(sources)
    summaries = "; ".join(memory.summary for memory in memories[:3])
    return (
        f"I found {len(memories)} relevant local "
        f"{'activity record' if len(memories) == 1 else 'activity records'} "
        f"from {source_phrase}. Strongest evidence: {summaries}."
    )


def ask_memory(db: Session, *, query: str, limit: int) -> AskMemoryResponse:
    ensure_memories_for_events(db)
    now = datetime.now(UTC)
    ranked_memories = rank_memories(db, query=query, limit=limit, now=now)
    memories = [
        DerivedMemoryRead(
            id=memory.id,
            occurred_at=memory.occurred_at,
            source=Source(memory.source),
            summary=memory.summary,
            keywords=memory.keywords,
            model_id=(
                embedding.model
                if (embedding := db.get(MemoryEmbedding, memory.id)) is not None
                else "local-legacy-metadata-v1"
            ),
            score=round(score, 3),
            evidence=evidence_for_memory(db, memory.id),
            links=links_for_memory(db, memory.id),
        )
        for memory, score in ranked_memories
    ]
    return AskMemoryResponse(
        query=query,
        answer=answer_for_memories(query, memories),
        retrieval_method="local lexical ranking + feature-hash similarity",
        memories=memories,
        generated_at=now,
    )


def ask_memory_with_gemini(
    db: Session,
    *,
    query: str,
    limit: int,
) -> AskMemoryResponse:
    """Use Gemini only after an explicit user action, over click-approved excerpts."""

    local_result = ask_memory(db, query=query, limit=limit)
    evidence: list[dict[str, Any]] = []
    remaining_characters = 6_000

    for memory in local_result.memories:
        for item in memory.evidence:
            event = item.event
            raw_excerpt = event.payload.get("context_excerpt")
            excerpt = str(raw_excerpt).strip() if isinstance(raw_excerpt, str) else ""
            summary = str(
                event.payload.get("context_summary") or memory.summary or ""
            ).strip()
            raw_topics = event.payload.get("context_topics")
            topics = (
                [str(t) for t in raw_topics] if isinstance(raw_topics, list) else []
            )
            description = str(event.payload.get("description") or "").strip()

            if (
                event.source not in (Source.BROWSER, Source.YOUTUBE, Source.DOCUMENT)
                or event.event_type != "tab_understood"
                or (not excerpt and not summary)
                or remaining_characters <= 0
            ):
                continue

            summary_budget = min(len(summary), remaining_characters)
            remaining_characters -= summary_budget
            bounded_excerpt = excerpt[:remaining_characters]
            remaining_characters -= len(bounded_excerpt)

            evidence_entry: dict[str, Any] = {
                "title": event.title or "Untitled tab",
                "host": str(event.payload.get("host", "")),
                "path": str(event.payload.get("path", "/")),
                "summary": summary[:summary_budget],
                "topics": topics,
                "description": description,
                "excerpt": bounded_excerpt,
            }
            # Include YouTube-specific metadata for richer context
            if event.source is Source.YOUTUBE:
                video_id = event.payload.get("video_id")
                channel = event.payload.get("channel")
                if video_id:
                    evidence_entry["video_id"] = str(video_id)
                if channel:
                    evidence_entry["channel"] = str(channel)

            evidence.append(evidence_entry)

    if not evidence:
        raise GeminiRequestError(
            "No matching click-approved tab context was found. Use Understand this tab first."
        )

    answer = answer_tab_question(query, evidence)
    record_privacy_action(
        db,
        direction="external",
        provider="gemini",
        action="ask_with_gemini",
        reason="explicit user-triggered Gemini retrieval over approved tab excerpts",
        bytes_count=sum(
            len(str(value).encode("utf-8"))
            for item in evidence
            for value in item.values()
        ),
        metadata={"evidence_items": len(evidence)},
    )
    return local_result.model_copy(
        update={
            "answer": answer,
            "retrieval_method": (
                "local retrieval + Gemini answer over click-approved tab excerpts"
            ),
        }
    )


def delete_derived_memories_for_events(
    db: Session,
    event_ids: Iterable[str],
) -> int:
    event_id_list = list(event_ids)
    if not event_id_list:
        return 0

    memory_ids = list(
        db.scalars(
            select(MemoryEvidence.memory_id).where(
                MemoryEvidence.event_id.in_(event_id_list)
            )
        ).all()
    )
    if not memory_ids:
        return 0

    db.execute(
        delete(SemanticEmbedding).where(SemanticEmbedding.memory_id.in_(memory_ids))
    )
    db.execute(
        delete(MemoryLifecycle).where(MemoryLifecycle.memory_id.in_(memory_ids))
    )
    db.execute(
        delete(ProjectMemory).where(ProjectMemory.memory_id.in_(memory_ids))
    )
    db.execute(delete(GoalMemory).where(GoalMemory.memory_id.in_(memory_ids)))
    db.execute(
        delete(MemoryLink).where(
            MemoryLink.source_memory_id.in_(memory_ids)
            | MemoryLink.target_memory_id.in_(memory_ids)
        )
    )
    db.execute(
        delete(MemoryEmbedding).where(MemoryEmbedding.memory_id.in_(memory_ids))
    )
    db.execute(
        delete(MemoryEvidence).where(MemoryEvidence.memory_id.in_(memory_ids))
    )
    db.execute(delete(DerivedMemory).where(DerivedMemory.id.in_(memory_ids)))
    return len(memory_ids)


def delete_all_derived_memory_data(db: Session) -> None:
    db.execute(delete(SemanticEmbedding))
    db.execute(delete(MemoryLifecycle))
    db.execute(delete(ProjectMemory))
    db.execute(delete(GoalMemory))
    db.execute(delete(MemoryLink))
    db.execute(delete(MemoryEmbedding))
    db.execute(delete(MemoryEvidence))
    db.execute(delete(DerivedMemory))
