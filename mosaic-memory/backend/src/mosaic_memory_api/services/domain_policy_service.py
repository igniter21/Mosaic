from __future__ import annotations

from fnmatch import fnmatch

from sqlalchemy import select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.privacy_models import SourceDomainRule
from mosaic_memory_api.domain.events import Source


class PrivacyPolicyDeniedError(RuntimeError):
    """Raised when a source/domain rule explicitly blocks event storage."""


def list_domain_rules(
    db: Session, source: Source | None = None
) -> list[SourceDomainRule]:
    stmt = select(SourceDomainRule).order_by(
        SourceDomainRule.source.asc(), SourceDomainRule.pattern.asc()
    )
    if source is not None:
        stmt = stmt.where(SourceDomainRule.source == source.value)
    return list(db.scalars(stmt).all())


def upsert_domain_rule(
    db: Session,
    *,
    source: Source,
    pattern: str,
    action: str = "deny",
    enabled: bool = True,
) -> SourceDomainRule:
    pattern = pattern.strip().lower()
    action = action.lower().strip()
    if not pattern:
        raise ValueError("pattern must not be empty")
    if action not in {"allow", "deny"}:
        raise ValueError("action must be allow or deny")
    row = db.scalar(
        select(SourceDomainRule).where(
            SourceDomainRule.source == source.value,
            SourceDomainRule.pattern == pattern,
        )
    )
    if row is None:
        row = SourceDomainRule(
            source=source.value, pattern=pattern, action=action, enabled=enabled
        )
        db.add(row)
    else:
        row.action = action
        row.enabled = enabled
    db.commit()
    db.refresh(row)
    return row


def delete_domain_rule(db: Session, rule_id: str) -> bool:
    row = db.get(SourceDomainRule, rule_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def domain_is_allowed(db: Session, source: Source | str, host: str | None) -> bool:
    """Evaluate explicit domain rules. No rules means allow; deny wins over allow."""
    if not host:
        return True
    source_val = source.value if isinstance(source, Source) else str(source)
    normalized = host.strip().lower().split(":", 1)[0]
    rows = list(
        db.scalars(
            select(SourceDomainRule).where(
                SourceDomainRule.source == source_val,
                SourceDomainRule.enabled.is_(True),
            )
        ).all()
    )
    matched = [
        row
        for row in rows
        if fnmatch(normalized, row.pattern)
        or fnmatch(normalized, row.pattern.lstrip("*."))
    ]
    if any(row.action == "deny" for row in matched):
        return False
    if any(row.action == "allow" for row in matched):
        return True
    return True


def enforce_domain_policy(db: Session, source: Source | str, host: str | None) -> None:
    if domain_is_allowed(db, source, host):
        return
    source_val = source.value if isinstance(source, Source) else str(source)
    raise PrivacyPolicyDeniedError(
        f"The {source_val} source is blocked for host '{host}' by a local privacy rule."
    )
