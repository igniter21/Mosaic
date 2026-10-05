from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.base import Base
from mosaic_memory_api.db.context_models import ActivitySession, Goal, Project
from mosaic_memory_api.db.models import DerivedMemory, MemoryEvidence, RawEvent
from mosaic_memory_api.db.semantic_models import SemanticEmbedding
from mosaic_memory_api.services import semantic_index
from mosaic_memory_api.services.context_engine import (
    project_key_for_event,
    rebuild_sessions,
)
from mosaic_memory_api.services.learning_service import learning_graph


def test_context_upgrade_rebuilds_sessions_and_project_links() -> None:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    # Tests may be run in the real application package where all models are already imported.
    import mosaic_memory_api.db.context_models
    import mosaic_memory_api.db.semantic_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = Session(engine)
    now = datetime.now(UTC).replace(microsecond=0)
    event = RawEvent(
        id="evt-test-1",
        occurred_at=now,
        source="git",
        event_type="commit",
        title="Implement retrieval",
        payload={"repository_name": "Mosaic", "message": "Implement retrieval"},
        privacy_level="normal",
        retention_class="long_term",
    )
    memory = DerivedMemory(
        id="mem-test-1",
        occurred_at=now,
        source="git",
        summary="Implement retrieval",
        keywords=["retrieval", "mosaic"],
    )
    db.add_all([event, memory])
    db.flush()
    db.add(MemoryEvidence(memory_id=memory.id, event_id=event.id))
    db.add(Goal(title="Improve retrieval", description="Mosaic retrieval"))
    db.commit()

    assert project_key_for_event(event) == "Mosaic"
    assert rebuild_sessions(db) == 1
    assert db.scalar(select(ActivitySession)) is not None
    assert db.scalar(select(Project)) is not None
    db.close()


def test_learning_graph_omits_generic_domain_keywords() -> None:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    db = Session(engine)
    db.add(
        DerivedMemory(
            id="mem-learning-1",
            occurred_at=datetime.now(UTC),
            source="browser",
            summary="Read about local retrieval.",
            keywords=["169", "com", "localhost", "mosaic", "retrieval", "watch"],
        )
    )
    db.commit()

    graph = learning_graph(db)

    assert [concept.concept for concept in graph.concepts] == ["retrieval"]
    db.close()


def test_semantic_scoring_skips_model_loading_without_an_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    db = Session(engine)
    db.add(
        DerivedMemory(
            id="mem-semantic-1",
            occurred_at=datetime.now(UTC),
            source="browser",
            summary="Read about local retrieval.",
            keywords=["retrieval"],
        )
    )
    db.add(
        SemanticEmbedding(
            memory_id="mem-semantic-1",
            model="sentence-transformers",
            dimensions=2,
            vector=[0.5, 0.5],
        )
    )
    db.commit()
    monkeypatch.setattr(semantic_index, "semantic_available", lambda: False)
    monkeypatch.setattr(
        semantic_index,
        "embed",
        lambda _texts: pytest.fail("The model must not load without embeddings."),
    )

    assert semantic_index.semantic_scores(db, "retrieval", ["mem-semantic-1"]) == {}
    db.close()



def test_semantic_scoring_computes_scores_when_model_is_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    db = Session(engine)
    db.add(
        SemanticEmbedding(
            memory_id="mem-semantic-1",
            model="sentence-transformers",
            dimensions=2,
            vector=[0.6, 0.8],
        )
    )
    db.commit()
    monkeypatch.setattr(semantic_index, "semantic_available", lambda: True)
    monkeypatch.setattr(semantic_index, "embed", lambda _texts: [[0.6, 0.8]])

    scores = semantic_index.semantic_scores(db, "retrieval", ["mem-semantic-1"])
    assert scores == pytest.approx({"mem-semantic-1": 1.0})
    db.close()


def test_build_resume_context_reconstructs_summary() -> None:
    from mosaic_memory_api.services.resume_service import build_resume_context
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    db = Session(engine)

    resume = build_resume_context(db)
    assert resume.title is not None
    assert resume.summary is not None
    assert isinstance(resume.suggested_next_steps, list)
    assert isinstance(resume.memories, list)
    db.close()
