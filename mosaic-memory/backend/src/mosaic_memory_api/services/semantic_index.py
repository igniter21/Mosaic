from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.models import DerivedMemory
from mosaic_memory_api.db.semantic_models import SemanticEmbedding
from mosaic_memory_api.services.semantic_service import (
    embed,
    semantic_available,
    semantic_model_loaded,
)


def reindex_semantic_embeddings(db: Session) -> int:
    if not semantic_available():
        raise RuntimeError(
            "sentence-transformers is not installed. Install the context extra first."
        )
    memories = list(
        db.scalars(
            select(DerivedMemory).order_by(DerivedMemory.occurred_at.asc())
        ).all()
    )
    if not memories:
        return 0
    texts = [
        f"{memory.source} {memory.summary} {' '.join(memory.keywords)}"
        for memory in memories
    ]
    vectors = embed(texts)
    for memory, vector in zip(memories, vectors, strict=True):
        row = db.get(SemanticEmbedding, memory.id)
        if row is None:
            row = SemanticEmbedding(
                memory_id=memory.id,
                model="sentence-transformers",
                dimensions=len(vector),
                vector=vector,
            )
            db.add(row)
        else:
            row.model = "sentence-transformers"
            row.dimensions = len(vector)
            row.vector = vector
    db.commit()
    return len(memories)


def semantic_scores(db: Session, query: str, memory_ids: list[str]) -> dict[str, float]:
    if not memory_ids or not semantic_available() or not semantic_model_loaded():
        return {}
    rows = list(
        db.scalars(
            select(SemanticEmbedding).where(SemanticEmbedding.memory_id.in_(memory_ids))
        ).all()
    )
    # The feature-hash path remains responsive unless the optional model has
    # already been loaded through the explicit semantic-index action.
    if not rows:
        return {}
    try:
        query_vector = embed([query])[0]
    except (ImportError, OSError, RuntimeError, ValueError):
        return {}
    scores: dict[str, float] = {}
    for row in rows:
        if len(row.vector) != len(query_vector):
            continue
        score = sum(a * b for a, b in zip(query_vector, row.vector, strict=True))
        scores[row.memory_id] = max(0.0, min(1.0, float(score)))
    return scores
