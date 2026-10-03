from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mosaic_memory_api.db.base import Base
from mosaic_memory_api.db.types import UtcDateTime


class SourceDomainRule(Base):
    __tablename__ = "source_domain_rules"
    __table_args__ = (UniqueConstraint("source", "pattern"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    source: Mapped[str] = mapped_column(String(50), index=True)
    pattern: Mapped[str] = mapped_column(String(300), index=True)
    action: Mapped[str] = mapped_column(String(20), default="deny")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=lambda: datetime.now(UTC), index=True
    )
