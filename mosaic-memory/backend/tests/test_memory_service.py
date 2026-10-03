from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from mosaic_memory_api.db.base import Base
from mosaic_memory_api.db.models import (
    DerivedMemory,
    MemoryEmbedding,
    MemoryEvidence,
    RawEvent,
    SourceSetting,
)
from mosaic_memory_api.db.session import get_db
from mosaic_memory_api.domain.events import EventCreate, Source
from mosaic_memory_api.domain.tab_context import TabContextRequest
from mosaic_memory_api.main import app
from mosaic_memory_api.services import memory_service, tab_context_service
from mosaic_memory_api.services.event_service import create_event
from mosaic_memory_api.services.gemini_service import GeminiTabUnderstanding
from mosaic_memory_api.services.memory_service import (
    ask_memory,
    build_memory_for_event,
)
from mosaic_memory_api.services.privacy_service import delete_events_by_filter
from mosaic_memory_api.services.source_model_router import model_for_source


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys = ON")

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def add_event(
    db: Session,
    *,
    source: Source,
    event_type: str,
    title: str,
    occurred_at: datetime | None = None,
) -> RawEvent:
    raw_event = RawEvent(
        id=str(uuid4()),
        occurred_at=occurred_at or datetime.now(UTC),
        source=source.value,
        event_type=event_type,
        title=title,
        payload={},
        privacy_level="normal",
        retention_class="short_term",
    )
    db.add(raw_event)
    db.flush()
    build_memory_for_event(db, raw_event)
    db.commit()
    return raw_event


def test_ask_memory_returns_ranked_memories_with_raw_evidence_and_links(
    db: Session,
) -> None:
    first_event = add_event(
        db,
        source=Source.YOUTUBE,
        event_type="video_viewed",
        title="Python sorting tutorial",
    )
    add_event(
        db,
        source=Source.LEETCODE,
        event_type="problem_viewed",
        title="Python array practice",
    )

    response = ask_memory(
        db,
        query="What was I learning about Python?",
        limit=5,
    )

    assert response.memories
    assert response.memories[0].summary == "Watched Python sorting tutorial"
    assert str(response.memories[0].evidence[0].event.event_id) == first_event.id
    assert response.memories[0].score > 0
    assert response.memories[0].model_id == "local-video-metadata-v1"
    assert response.memories[1].links
    assert "Strongest evidence" in response.answer
    assert (
        response.retrieval_method == "local lexical ranking + feature-hash similarity"
    )


def test_ingestion_creates_a_derived_memory_and_embedding_automatically(
    db: Session,
) -> None:
    db.add(SourceSetting(source=Source.YOUTUBE.value, enabled=True))
    db.commit()

    event = create_event(
        db,
        EventCreate(
            source=Source.YOUTUBE,
            event_type="video_viewed",
            title="Local retrieval walkthrough",
        ),
    )

    memory = db.scalar(select(DerivedMemory))
    assert memory is not None
    assert memory.summary == "Watched Local retrieval walkthrough"
    embedding = db.get(MemoryEmbedding, memory.id)
    assert embedding is not None
    assert embedding.model == "local-video-metadata-v1"
    assert (
        db.scalar(select(MemoryEvidence).where(MemoryEvidence.event_id == event.id))
        is not None
    )


@pytest.mark.parametrize(
    ("source", "event_type"),
    [
        (Source.BROWSER, "page_viewed"),
        (Source.YOUTUBE, "video_viewed"),
        (Source.LEETCODE, "problem_viewed"),
        (Source.VSCODE, "document_saved"),
        (Source.DOCUMENT, "document_indexed"),
    ],
)
def test_each_source_routes_to_its_own_local_model(
    db: Session,
    source: Source,
    event_type: str,
) -> None:
    event = add_event(
        db,
        source=source,
        event_type=event_type,
        title="Routing regression test",
    )
    memory_id = db.scalar(
        select(MemoryEvidence.memory_id).where(MemoryEvidence.event_id == event.id)
    )

    assert memory_id is not None
    embedding = db.get(MemoryEmbedding, memory_id)
    assert embedding is not None
    assert embedding.model == model_for_source(source).model_id


def test_sqlite_events_restore_utc_timezone_information(db: Session) -> None:
    occurred_at = datetime(2026, 9, 21, 18, 56, tzinfo=UTC)
    event = add_event(
        db,
        source=Source.YOUTUBE,
        event_type="video_viewed",
        title="Timezone regression test",
        occurred_at=occurred_at,
    )

    db.expire_all()
    reloaded = db.get(RawEvent, event.id)

    assert reloaded is not None
    assert reloaded.occurred_at == occurred_at
    assert reloaded.occurred_at.tzinfo is UTC


def test_event_api_returns_sqlite_timestamps_with_a_utc_offset(db: Session) -> None:
    occurred_at = datetime(2026, 9, 21, 18, 56, tzinfo=UTC)
    add_event(
        db,
        source=Source.YOUTUBE,
        event_type="video_viewed",
        title="Timezone API regression test",
        occurred_at=occurred_at,
    )
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/events")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    returned_time = datetime.fromisoformat(response.json()[0]["occurred_at"])
    assert returned_time == occurred_at
    assert returned_time.tzinfo is UTC


def test_source_settings_expose_the_selected_local_model(db: Session) -> None:
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/sources")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    source_models = {
        setting["source"]: setting["model_id"] for setting in response.json()
    }
    assert source_models["youtube"] == "local-video-metadata-v1"
    assert source_models["vscode"] == "local-code-workspace-metadata-v1"


def test_click_only_tab_understanding_stores_bounded_sensitive_evidence(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.add(SourceSetting(source=Source.BROWSER.value, enabled=True))
    db.commit()
    request = TabContextRequest(
        title="A local privacy guide",
        host="example.com",
        path="/privacy-guide",
        context_text="Important privacy detail. " * 200,
    )
    expected_understanding = GeminiTabUnderstanding(
        model_id="gemini-test-model",
        summary="The guide explains privacy controls for local browser context.",
        topics=["privacy", "browser context"],
    )
    monkeypatch.setattr(
        tab_context_service,
        "understand_tab_context",
        lambda _request: expected_understanding,
    )

    event, understanding = tab_context_service.understand_and_store_tab(db, request)

    assert understanding == expected_understanding
    assert event.source == Source.BROWSER.value
    assert event.event_type == "tab_understood"
    assert event.privacy_level == "sensitive"
    assert event.payload["context_summary"] == expected_understanding.summary
    assert event.payload["context_topics"] == expected_understanding.topics
    assert len(event.payload["context_excerpt"]) == 2_500

    memory = db.scalar(select(DerivedMemory))
    assert memory is not None
    assert memory.summary.startswith("Understood A local privacy guide:")
    assert "privacy" in memory.keywords


def test_ask_with_gemini_uses_only_click_approved_tab_evidence(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.add(SourceSetting(source=Source.BROWSER.value, enabled=True))
    db.commit()
    request = TabContextRequest(
        title="A retrieval guide",
        host="example.com",
        path="/retrieval",
        context_text="Retrieval systems use evidence to answer questions accurately. "
        * 80,
    )
    monkeypatch.setattr(
        tab_context_service,
        "understand_tab_context",
        lambda _request: GeminiTabUnderstanding(
            model_id="gemini-test-model",
            summary="The guide explains evidence-grounded retrieval.",
            topics=["retrieval", "evidence"],
        ),
    )
    tab_context_service.understand_and_store_tab(db, request)
    captured_evidence: list[dict[str, str]] = []

    def fake_answer(query: str, evidence: list[dict[str, str]]) -> str:
        assert query == "How does retrieval stay accurate?"
        captured_evidence.extend(evidence)
        return "It stays accurate by grounding answers in retrieved evidence."

    monkeypatch.setattr(memory_service, "answer_tab_question", fake_answer)
    response = memory_service.ask_memory_with_gemini(
        db,
        query="How does retrieval stay accurate?",
        limit=5,
    )

    assert (
        response.answer
        == "It stays accurate by grounding answers in retrieved evidence."
    )
    assert response.retrieval_method.startswith("local retrieval + Gemini")
    assert captured_evidence[0]["title"] == "A retrieval guide"
    assert "Retrieval systems" in captured_evidence[0]["excerpt"]
    assert (
        captured_evidence[0]["summary"]
        == "The guide explains evidence-grounded retrieval."
    )
    assert captured_evidence[0]["topics"] == ["retrieval", "evidence"]


def test_tab_context_rejects_url_query_data() -> None:
    with pytest.raises(ValueError, match="exclude query strings"):
        TabContextRequest(
            title="Unsafe path",
            host="example.com",
            path="/account?token=not-allowed",
            context_text="This contains enough text to validate the request safely. "
            * 2,
        )


def test_time_bounded_question_returns_recent_activity_without_a_topic_term(
    db: Session,
) -> None:
    add_event(
        db,
        source=Source.BROWSER,
        event_type="page_viewed",
        title="Recent research",
        occurred_at=datetime.now(UTC) - timedelta(days=2),
    )
    add_event(
        db,
        source=Source.BROWSER,
        event_type="page_viewed",
        title="Old research",
        occurred_at=datetime.now(UTC) - timedelta(days=10),
    )

    response = ask_memory(db, query="What did I do last week?", limit=5)

    assert [memory.summary for memory in response.memories] == [
        "Visited Recent research"
    ]


def test_deleting_raw_events_also_removes_derived_memory_and_embeddings(
    db: Session,
) -> None:
    add_event(
        db,
        source=Source.DOCUMENT,
        event_type="document_indexed",
        title="Project brief",
    )

    deleted_count = delete_events_by_filter(
        db,
        source=Source.DOCUMENT,
        from_time=None,
        to_time=None,
    )

    assert deleted_count == 1
    assert db.scalar(select(func.count()).select_from(RawEvent)) == 0
    assert db.scalar(select(func.count()).select_from(DerivedMemory)) == 0
    assert db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 0


def test_ask_endpoint_returns_an_evidence_backed_response(db: Session) -> None:
    event = add_event(
        db,
        source=Source.VSCODE,
        event_type="document_saved",
        title="src/retrieval.py",
    )
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/memory/ask",
                json={"query": "What code did I work on?"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["memories"][0]["evidence"][0]["event"]["event_id"] == event.id
    assert body["memories"][0]["source"] == "vscode"
    assert body["memories"][0]["model_id"] == "local-code-workspace-metadata-v1"


def test_event_deduplication_coalesces_recent_events(db: Session) -> None:
    from mosaic_memory_api.services.privacy_service import set_source_enabled

    set_source_enabled(db, Source.BROWSER, True)
    t0 = datetime(2026, 10, 3, 12, 0, 0, tzinfo=UTC)
    t1 = t0 + timedelta(minutes=2)

    event1_in = EventCreate(
        event_id=str(uuid4()),
        occurred_at=t0,
        source=Source.BROWSER,
        event_type="page_viewed",
        title="Python Documentation",
        payload={"host": "docs.python.org", "path": "/3/library/sqlite3.html"},
        privacy_level="normal",
        retention_class="short_term",
    )
    event1 = create_event(db, event1_in)
    assert event1.visit_count == 1

    event2_in = EventCreate(
        event_id=str(uuid4()),
        occurred_at=t1,
        source=Source.BROWSER,
        event_type="page_viewed",
        title="Python Documentation - SQLite",
        payload={"host": "docs.python.org", "path": "/3/library/sqlite3.html"},
        privacy_level="normal",
        retention_class="short_term",
    )
    event2 = create_event(db, event2_in)

    # Should coalesce into the same record
    assert event2.id == event1.id
    assert event2.visit_count == 2
    assert event2.first_seen_at == t0
    assert event2.occurred_at == t1
    assert db.scalar(select(func.count()).select_from(RawEvent)) == 1


def test_distinct_events_are_not_coalesced(db: Session) -> None:
    from mosaic_memory_api.services.privacy_service import set_source_enabled

    set_source_enabled(db, Source.BROWSER, True)
    t0 = datetime(2026, 10, 3, 12, 0, 0, tzinfo=UTC)

    event1 = create_event(
        db,
        EventCreate(
            event_id=str(uuid4()),
            occurred_at=t0,
            source=Source.BROWSER,
            event_type="page_viewed",
            title="Page 1",
            payload={"host": "example.com", "path": "/page1"},
            privacy_level="normal",
            retention_class="short_term",
        ),
    )
    event2 = create_event(
        db,
        EventCreate(
            event_id=str(uuid4()),
            occurred_at=t0 + timedelta(minutes=1),
            source=Source.BROWSER,
            event_type="page_viewed",
            title="Page 2",
            payload={"host": "example.com", "path": "/page2"},
            privacy_level="normal",
            retention_class="short_term",
        ),
    )

    assert event1.id != event2.id
    assert event1.visit_count == 1
    assert event2.visit_count == 1
    assert db.scalar(select(func.count()).select_from(RawEvent)) == 2


def test_erase_all_memory_clears_all_subsystems(db: Session) -> None:
    from mosaic_memory_api.db.context_models import (
        ActivitySession,
        ContextCapsule,
        Goal,
        Project,
        SessionEvent,
    )
    from mosaic_memory_api.services.privacy_service import erase_all_local_memory

    # Setup events, sessions, goals, projects
    ev = add_event(
        db,
        source=Source.GIT,
        event_type="commit",
        title="feat: add thing",
    )
    proj = Project(name="TestProj", slug="test-proj")
    goal = Goal(title="Goal 1", description="Do it")
    sess = ActivitySession(
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        summary="Working on project",
    )
    db.add_all([proj, goal, sess])
    db.flush()
    db.add(SessionEvent(session_id=sess.id, event_id=ev.id))
    db.add(ContextCapsule(title="Capsule 1", payload={"test": True}))
    db.commit()

    # Erase all
    result = erase_all_local_memory(db, "ERASE ALL LOCAL MEMORY")

    assert result.raw_events_deleted == 1
    assert db.scalar(select(func.count()).select_from(RawEvent)) == 0
    assert db.scalar(select(func.count()).select_from(DerivedMemory)) == 0
    assert db.scalar(select(func.count()).select_from(ActivitySession)) == 0
    assert db.scalar(select(func.count()).select_from(SessionEvent)) == 0
    assert db.scalar(select(func.count()).select_from(Goal)) == 0
    assert db.scalar(select(func.count()).select_from(Project)) == 0
    assert db.scalar(select(func.count()).select_from(ContextCapsule)) == 0

