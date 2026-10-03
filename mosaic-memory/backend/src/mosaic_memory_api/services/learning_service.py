from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.models import DerivedMemory
from mosaic_memory_api.domain.context import LearningConcept, LearningGraphRead

PRACTICE_WORDS = {
    "practice",
    "leetcode",
    "problem",
    "challenge",
    "exercise",
    "solve",
    "solved",
}
IMPLEMENT_WORDS = {
    "code",
    "coding",
    "programming",
    "implement",
    "implemented",
    "saved",
    "commit",
}
REVISION_WORDS = {"review", "revise", "revision", "revisit", "revisited", "again"}
LEARNING_STOP_WORDS = {
    "browser",
    "chatgpt",
    "com",
    "context",
    "desktop",
    "document",
    "file",
    "http",
    "https",
    "localhost",
    "memory",
    "mosaic",
    "open",
    "page",
    "project",
    "tab",
    "video",
    "watch",
    "www",
    "youtube",
}


def learning_graph(db: Session, limit: int = 30) -> LearningGraphRead:
    memories = list(
        db.scalars(
            select(DerivedMemory).order_by(DerivedMemory.occurred_at.asc())
        ).all()
    )
    buckets: dict[str, dict] = defaultdict(
        lambda: {
            "exposure_count": 0,
            "practice_count": 0,
            "implementation_count": 0,
            "revision_count": 0,
            "sources": set(),
            "first_seen_at": None,
            "last_seen_at": None,
        }
    )
    for memory in memories:
        for concept in memory.keywords:
            if concept.isdigit() or concept in LEARNING_STOP_WORDS:
                continue
            bucket = buckets[concept]
            bucket["exposure_count"] += 1
            bucket["sources"].add(memory.source)
            bucket["first_seen_at"] = bucket["first_seen_at"] or memory.occurred_at
            bucket["last_seen_at"] = memory.occurred_at
            terms = set(memory.keywords)
            if terms & PRACTICE_WORDS or memory.source == "leetcode":
                bucket["practice_count"] += 1
            if terms & IMPLEMENT_WORDS or memory.source in {"vscode", "git"}:
                bucket["implementation_count"] += 1
            if terms & REVISION_WORDS:
                bucket["revision_count"] += 1

    ranked = sorted(
        buckets.items(),
        key=lambda item: (
            item[1]["exposure_count"]
            + 2 * item[1]["practice_count"]
            + 2 * item[1]["implementation_count"],
            item[0],
        ),
        reverse=True,
    )[:limit]
    concepts = [
        LearningConcept(
            concept=name,
            exposure_count=data["exposure_count"],
            practice_count=data["practice_count"],
            implementation_count=data["implementation_count"],
            revision_count=data["revision_count"],
            sources=sorted(data["sources"]),
            first_seen_at=data["first_seen_at"],
            last_seen_at=data["last_seen_at"],
        )
        for name, data in ranked
    ]
    suggestions: list[str] = []
    for concept in concepts:
        if concept.exposure_count >= 3 and concept.practice_count == 0:
            suggestions.append(
                f"You have repeatedly encountered {concept.concept}; consider a practice task."
            )
        elif concept.implementation_count == 0 and concept.practice_count >= 2:
            suggestions.append(
                f"You have practiced {concept.concept}; consider implementing a small project feature."
            )
        elif concept.revision_count == 0 and concept.exposure_count >= 4:
            suggestions.append(
                f"You have seen {concept.concept} several times; consider scheduling a review."
            )
    return LearningGraphRead(concepts=concepts, suggestions=suggestions[:8])
