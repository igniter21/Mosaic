from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mosaic_memory_api.api.router import api_router
from mosaic_memory_api.core.config import get_settings
from mosaic_memory_api.db import (  # noqa: F401
    context_models,
    models,
    privacy_models,
    semantic_models,
)
from mosaic_memory_api.db.base import Base
from mosaic_memory_api.db.session import SessionLocal, engine
from mosaic_memory_api.services.lifecycle_service import run_lifecycle

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Lightweight column migration for existing databases.
    _migrate_dedup_columns()
    if settings.auto_forget:
        with SessionLocal() as db:
            run_lifecycle(db, execute=True)
    yield


def _migrate_dedup_columns() -> None:
    """Add visit_count / first_seen_at to raw_events if missing."""
    import sqlite3

    db_url = settings.database_url
    if not db_url.startswith("sqlite"):
        return
    db_path = db_url.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("PRAGMA table_info(raw_events)")
        columns = {row[1] for row in cursor.fetchall()}
        if "visit_count" not in columns:
            conn.execute(
                "ALTER TABLE raw_events ADD COLUMN visit_count INTEGER DEFAULT 1"
            )
        if "first_seen_at" not in columns:
            conn.execute(
                "ALTER TABLE raw_events ADD COLUMN first_seen_at TEXT"
            )
        conn.commit()
    finally:
        conn.close()


app = FastAPI(
    title="Mosaic Memory API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
