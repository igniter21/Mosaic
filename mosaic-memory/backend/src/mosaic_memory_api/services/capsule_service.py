from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from mosaic_memory_api.db.context_models import ContextCapsule
from mosaic_memory_api.domain.context import CapsuleCreate
from mosaic_memory_api.services.context_engine import (
    context_search,
    current_session,
    serialize_memory,
)
from mosaic_memory_api.services.policy_service import get_policy


def create_capsule(db: Session, request: CapsuleCreate) -> ContextCapsule:
    policy = get_policy(db, request.agent_name)
    ranked, receipt = context_search(
        db,
        query=request.title,
        limit=request.limit,
        project_id=request.project_id,
        goal_id=request.goal_id,
        allowed_sources=set(policy.allowed_sources),
        denied_sources=set(policy.denied_sources),
        deny_sensitive=policy.deny_sensitive,
        allowed_projects=set(policy.allowed_projects),
    )
    payload: dict[str, Any] = {
        "goal": request.title,
        "resume_prompt": f"Resume work on: {request.title}",
        "memories": [serialize_memory(db, memory, score) for memory, score in ranked],
        "active_session": current_session(db).model_dump(mode="json")
        if current_session(db)
        else None,
        "evidence_receipt": receipt,
        "created_by": request.agent_name,
        "version": 1,
    }
    capsule = ContextCapsule(
        title=request.title,
        project_id=request.project_id,
        goal_id=request.goal_id,
        expires_at=request.expires_at,
        payload=payload,
    )
    db.add(capsule)
    db.commit()
    db.refresh(capsule)
    return capsule


def get_capsule(db: Session, capsule_id: str) -> ContextCapsule | None:
    capsule = db.get(ContextCapsule, capsule_id)
    if capsule and capsule.expires_at and capsule.expires_at <= datetime.now(UTC):
        return None
    return capsule
