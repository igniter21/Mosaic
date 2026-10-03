from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from mosaic_memory_api.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def configure_sqlite(dbapi_connection, _) -> None:
    cursor = dbapi_connection.cursor()

    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA secure_delete = ON")
        cursor.execute("PRAGMA busy_timeout = 5000")
    finally:
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Generator[Session]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
