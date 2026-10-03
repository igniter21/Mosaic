from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.context_models import ContextPolicy, PrivacyLedgerEntry
from mosaic_memory_api.domain.context import ContextPolicyUpsert


def get_policy(db: Session, agent_name: str) -> ContextPolicy:
    policy = db.scalar(
        select(ContextPolicy).where(ContextPolicy.agent_name == agent_name)
    )
    if policy is None:
        policy = ContextPolicy(
            agent_name=agent_name,
            allowed_sources=[],
            denied_sources=[],
            allowed_projects=[],
            deny_sensitive=True,
            allow_external=False,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
    return policy


def upsert_policy(db: Session, request: ContextPolicyUpsert) -> ContextPolicy:
    policy = get_policy(db, request.agent_name)
    policy.allowed_sources = [source.value for source in request.allowed_sources]
    policy.denied_sources = [source.value for source in request.denied_sources]
    policy.allowed_projects = list(dict.fromkeys(request.allowed_projects))
    policy.deny_sensitive = request.deny_sensitive
    policy.allow_external = request.allow_external
    policy.updated_at = datetime.now(UTC)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def record_privacy_action(
    db: Session,
    *,
    direction: str,
    provider: str,
    action: str,
    source: str | None = None,
    bytes_count: int = 0,
    reason: str = "",
    metadata: dict | None = None,
) -> None:
    db.add(
        PrivacyLedgerEntry(
            direction=direction,
            provider=provider,
            action=action,
            source=source,
            bytes_count=max(0, bytes_count),
            reason=reason[:500],
            metadata_json=metadata or {},
        )
    )
    db.commit()
