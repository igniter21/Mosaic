from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.models import DerivedMemory
from mosaic_memory_api.db.semantic_models import SemanticEmbedding
from mosaic_memory_api.services.semantic_service import (
    embed,
    semantic_available,
    semantic_model_name,
)


def semantic_auto_index_enabled() -> bool:
    return os.getenv(
        "MOSAIC_AUTO_SEMANTIC_INDEX",
        "true",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def memory_text(memory: DerivedMemory) -> str:
    return (
        f"{memory.source} "
        f"{memory.summary} "
        f"{' '.join(memory.keywords)}"
    )


def index_memory_embedding(
    db: Session,
    memory: DerivedMemory,
    *,
    force: bool = False,
) -> bool:
    """
    Create or refresh the semantic embedding for one memory.

    Returns False instead of breaking event ingestion when the optional
    semantic dependency/model is unavailable.
    """
    if not semantic_available():
        return False

    model_name = semantic_model_name()

    existing = db.get(
        SemanticEmbedding,
        memory.id,
    )

    if (
        existing is not None
        and existing.model == model_name
        and existing.vector
        and not force
    ):
        return True

    try:
        vector = embed(
            [memory_text(memory)]
        )[0]
    except (
        ImportError,
        OSError,
        RuntimeError,
        ValueError,
    ):
        return False

    if existing is None:
        existing = SemanticEmbedding(
            memory_id=memory.id,
            model=model_name,
            dimensions=len(vector),
            vector=vector,
        )
        db.add(existing)
    else:
        existing.model = model_name
        existing.dimensions = len(vector)
        existing.vector = vector

    db.flush()
    return True


def ensure_semantic_embedding(
    db: Session,
    memory: DerivedMemory,
) -> bool:
    if not semantic_auto_index_enabled():
        return False

    return index_memory_embedding(
        db,
        memory,
    )


def reindex_semantic_embeddings(
    db: Session,
) -> int:
    if not semantic_available():
        raise RuntimeError(
            "sentence-transformers is not installed. "
            "Install the context extra first."
        )

    memories = list(
        db.scalars(
            select(DerivedMemory)
            .order_by(
                DerivedMemory.occurred_at.asc()
            )
        ).all()
    )

    indexed = 0

    for memory in memories:
        if index_memory_embedding(
            db,
            memory,
            force=True,
        ):
            indexed += 1

    db.commit()

    return indexed


def _score_rows(
    query: str,
    rows: list[SemanticEmbedding],
) -> dict[str, float]:
    if not rows:
        return {}

    try:
        query_vector = embed([query])[0]
    except (
        ImportError,
        OSError,
        RuntimeError,
        ValueError,
    ):
        return {}

    scores: dict[str, float] = {}

    for row in rows:
        if len(row.vector) != len(query_vector):
            continue

        score = sum(
            a * b
            for a, b in zip(
                query_vector,
                row.vector,
                strict=True,
            )
        )

        scores[row.memory_id] = max(
            0.0,
            min(
                1.0,
                float(score),
            ),
        )

    return scores


def semantic_scores(
    db: Session,
    query: str,
    memory_ids: list[str],
) -> dict[str, float]:
    if not memory_ids or not semantic_available():
        return {}

    rows = list(
        db.scalars(
            select(SemanticEmbedding).where(
                SemanticEmbedding.memory_id.in_(
                    memory_ids
                )
            )
        ).all()
    )

    return _score_rows(
        query,
        rows,
    )


def semantic_candidate_scores(
    db: Session,
    query: str,
    *,
    limit: int = 100,
) -> dict[str, float]:
    """
    Retrieve semantic candidates independently of lexical matching.

    This is the important Phase-1 change:
    semantic search can now discover memories that share meaning
    even when they do not share the exact same keywords.
    """
    if not semantic_available():
        return {}

    rows = list(
        db.scalars(
            select(SemanticEmbedding)
        ).all()
    )

    scores = _score_rows(
        query,
        rows,
    )

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    return dict(
        ranked[:limit]
    )