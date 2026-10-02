"""Database types that preserve UTC semantics across supported engines."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """Store instants in UTC and restore SQLite's missing timezone marker.

    SQLite persists ``DateTime`` values without an offset, even when the
    column is declared with ``timezone=True``. Mosaic stores all instants in
    UTC, so legacy offset-free values must be read back as UTC rather than as
    the browser's local timezone.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: object,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Datetime values must include a timezone offset.")
        return value.astimezone(UTC)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: object,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
