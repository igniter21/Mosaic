import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from mosaic_memory_api.db.base import Base
from mosaic_memory_api.db.models import DerivedMemory, RawEvent, SourceSetting
from mosaic_memory_api.db.session import get_db
from mosaic_memory_api.domain.events import Source
from mosaic_memory_api.domain.tab_context import TabContextRequest
from mosaic_memory_api.main import app
from mosaic_memory_api.services import memory_service, tab_context_service
from mosaic_memory_api.services.gemini_service import GeminiTabUnderstanding


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


MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
    b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"5 0 obj<</Length 49>>stream\n"
    b"BT /F1 12 Tf 100 700 Td (Offline Research Paper on Artificial Intelligence) Tj ET\n"
    b"endstream\n"
    b"endobj\n"
    b"xref\n"
    b"0 6\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"0000000216 00000 n \n"
    b"0000000282 00000 n \n"
    b"trailer<</Size 6/Root 1 0 R>>\n"
    b"startxref\n"
    b"382\n"
    b"%%EOF\n"
)


def test_offline_document_tab_understands_and_stores_as_document_source(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.add(SourceSetting(source=Source.DOCUMENT.value, enabled=True))
    db.commit()

    request = TabContextRequest(
        title="Local Saved Article",
        host="local-file",
        path="/C:/Users/rajri/Documents/article.html",
        context_text="This is an offline article about local-first software architecture and privacy."
        * 2,
        source="document",
    )
    expected = GeminiTabUnderstanding(
        model_id="gemini-test-model",
        summary="An article on local-first software and privacy.",
        topics=["local-first", "privacy", "offline"],
    )
    monkeypatch.setattr(
        tab_context_service,
        "understand_tab_context",
        lambda _req: expected,
    )

    event, understanding = tab_context_service.understand_and_store_tab(db, request)

    assert understanding == expected
    assert event.source == Source.DOCUMENT.value
    assert event.event_type == "tab_understood"
    assert event.payload["host"] == "local-file"
    assert event.payload["context_summary"] == expected.summary

    memory = db.scalar(
        select(DerivedMemory).where(DerivedMemory.source == Source.DOCUMENT.value)
    )
    assert memory is not None
    assert "Understood Local Saved Article:" in memory.summary
    assert "privacy" in memory.keywords


def test_pdf_endpoint_extracts_text_and_understands_document(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.add(SourceSetting(source=Source.DOCUMENT.value, enabled=True))
    db.commit()

    expected = GeminiTabUnderstanding(
        model_id="gemini-test-model",
        summary="A research paper on artificial intelligence systems.",
        topics=["research", "artificial intelligence", "offline"],
    )
    monkeypatch.setattr(
        tab_context_service,
        "understand_tab_context",
        lambda _req: expected,
    )

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/context/pdf",
                data={
                    "title": "AI Research Paper",
                    "host": "local-file",
                    "path": "/C:/Users/rajri/Downloads/paper.pdf",
                    "source": "document",
                },
                files={
                    "file": (
                        "paper.pdf",
                        io.BytesIO(MINIMAL_PDF_BYTES),
                        "application/pdf",
                    )
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["summary"] == expected.summary
    assert body["event"]["source"] == "document"

    # Verify event stored in DB
    raw_event = db.scalar(
        select(RawEvent).where(RawEvent.source == Source.DOCUMENT.value)
    )
    assert raw_event is not None
    assert "Artificial Intelligence" in raw_event.payload["context_excerpt"]


def test_ask_memory_with_gemini_includes_document_evidence(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.add(SourceSetting(source=Source.DOCUMENT.value, enabled=True))
    db.commit()

    request = TabContextRequest(
        title="Privacy Architecture Whitepaper",
        host="local-file",
        path="/C:/Users/rajri/Documents/whitepaper.pdf",
        context_text="The whitepaper details how zero-knowledge local memory preserves privacy.",
        source="document",
    )
    monkeypatch.setattr(
        tab_context_service,
        "understand_tab_context",
        lambda _req: GeminiTabUnderstanding(
            model_id="gemini-test-model",
            summary="A whitepaper on zero-knowledge local memory architectures.",
            topics=["zero-knowledge", "privacy", "whitepaper"],
        ),
    )
    tab_context_service.understand_and_store_tab(db, request)

    captured_evidence = []

    def fake_answer(query: str, evidence: list[dict]) -> str:
        captured_evidence.extend(evidence)
        return "The whitepaper outlines zero-knowledge local memory."

    monkeypatch.setattr(memory_service, "answer_tab_question", fake_answer)

    response = memory_service.ask_memory_with_gemini(
        db,
        query="What did the privacy whitepaper say?",
        limit=5,
    )

    assert response.answer == "The whitepaper outlines zero-knowledge local memory."
    assert captured_evidence[0]["title"] == "Privacy Architecture Whitepaper"
    assert captured_evidence[0]["host"] == "local-file"
    assert "zero-knowledge" in captured_evidence[0]["summary"]


def test_pdf_endpoint_reads_from_local_disk_when_no_file_uploaded(
    tmp_path,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.add(SourceSetting(source=Source.DOCUMENT.value, enabled=True))
    db.commit()

    pdf_file = tmp_path / "offline_paper.pdf"
    pdf_file.write_bytes(MINIMAL_PDF_BYTES)

    expected = GeminiTabUnderstanding(
        model_id="gemini-test-model",
        summary="An offline paper read directly from disk without browser injection.",
        topics=["offline", "disk", "research"],
    )
    monkeypatch.setattr(
        tab_context_service,
        "understand_tab_context",
        lambda _req: expected,
    )

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            # Send without file upload, passing local path (even with leading slash as browser does)
            response = client.post(
                "/api/v1/context/pdf",
                data={
                    "title": "Offline Disk Paper",
                    "host": "local-file",
                    "path": f"/{pdf_file.as_posix()}",
                    "source": "document",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["summary"] == expected.summary
    assert body["event"]["source"] == "document"


def test_pdf_endpoint_handles_url_encoded_path_with_spaces_and_parentheses(
    tmp_path,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.add(SourceSetting(source=Source.DOCUMENT.value, enabled=True))
    db.commit()

    pdf_file = tmp_path / "Normal People (Sally Rooney).pdf"
    pdf_file.write_bytes(MINIMAL_PDF_BYTES)

    expected = GeminiTabUnderstanding(
        model_id="gemini-test-model",
        summary="A novel excerpt about Normal People.",
        topics=["fiction", "literature"],
    )
    monkeypatch.setattr(
        tab_context_service,
        "understand_tab_context",
        lambda _req: expected,
    )

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            # Simulate browser sending percent-encoded path e.g. Normal%20People%20(Sally%20Rooney).pdf
            encoded_path = f"/{pdf_file.as_posix()}".replace(" ", "%20")
            response = client.post(
                "/api/v1/context/pdf",
                data={
                    "title": "Normal People",
                    "host": "local-file",
                    "path": encoded_path,
                    "source": "document",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["summary"] == expected.summary
    assert body["event"]["source"] == "document"


def test_tab_endpoint_reads_local_html_from_disk_when_context_text_empty(
    tmp_path,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db.add(SourceSetting(source=Source.DOCUMENT.value, enabled=True))
    db.commit()

    html_file = tmp_path / "offline_article.html"
    html_file.write_text(
        "<html><head><title>Disk Article</title></head><body><p>This is a complete offline article read directly from the user's hard drive.</p></body></html>",
        encoding="utf-8",
    )

    expected = GeminiTabUnderstanding(
        model_id="gemini-test-model",
        summary="A local offline article read from the filesystem.",
        topics=["local", "offline", "disk"],
    )
    monkeypatch.setattr(
        tab_context_service,
        "understand_tab_context",
        lambda _req: expected,
    )

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/context/tab",
                json={
                    "title": "Offline Article",
                    "host": "local-file",
                    "path": f"/{html_file.as_posix()}",
                    "context_text": "",
                    "source": "document",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["summary"] == expected.summary
    assert body["event"]["source"] == "document"
