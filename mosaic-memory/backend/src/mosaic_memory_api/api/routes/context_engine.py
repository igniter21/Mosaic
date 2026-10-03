from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from mosaic_memory_api.db.context_models import (
    Goal,
    PrivacyLedgerEntry,
    Project,
)
from mosaic_memory_api.db.session import get_db
from mosaic_memory_api.domain.context import (
    CapsuleCreate,
    CapsuleRead,
    ContextAskRequest,
    ContextPolicyRead,
    ContextPolicyUpsert,
    ContextResult,
    GoalCreate,
    GoalRead,
    GoalUpdate,
    LearningGraphRead,
    LifecyclePreview,
    LifecycleRunRequest,
    LifecycleRunResult,
    PrivacyLedgerRead,
    ProjectCreate,
    ProjectRead,
    SessionDetailRead,
    SessionRead,
)
from mosaic_memory_api.services.capsule_service import create_capsule, get_capsule
from mosaic_memory_api.services.context_engine import (
    context_search,
    current_session,
    get_or_create_project,
    list_sessions,
    rebuild_sessions,
    serialize_memory,
    session_detail,
)
from mosaic_memory_api.services.learning_service import learning_graph
from mosaic_memory_api.services.lifecycle_service import (
    preview_lifecycle,
    run_lifecycle,
)
from mosaic_memory_api.services.policy_service import get_policy, upsert_policy
from mosaic_memory_api.services.semantic_index import reindex_semantic_embeddings

router = APIRouter()


@router.post("/rebuild", response_model=dict[str, int])
def rebuild_context(db: Session = Depends(get_db)) -> dict[str, int]:
    return {"sessions_rebuilt": rebuild_sessions(db)}


@router.get("/sessions", response_model=list[SessionRead])
def get_sessions(
    limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)
) -> list[SessionRead]:
    return list_sessions(db, limit=limit)


@router.get("/sessions/{session_id}", response_model=SessionDetailRead)
def get_session_detail(
    session_id: str, db: Session = Depends(get_db)
) -> SessionDetailRead:
    detail = session_detail(db, session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return detail


@router.get("/resume", response_model=SessionRead | None)
def resume_context(db: Session = Depends(get_db)) -> SessionRead | None:
    return current_session(db)


@router.post("/ask", response_model=ContextResult)
def ask_context(
    request: ContextAskRequest, db: Session = Depends(get_db)
) -> ContextResult:
    policy = get_policy(db, request.agent_name)
    ranked, receipt = context_search(
        db,
        query=request.query,
        limit=request.limit,
        project_id=request.project_id,
        goal_id=request.goal_id,
        source=request.source,
        allowed_sources=set(policy.allowed_sources),
        denied_sources=set(policy.denied_sources),
        deny_sensitive=policy.deny_sensitive,
        allowed_projects=set(policy.allowed_projects),
    )
    memories = [serialize_memory(db, memory, score) for memory, score in ranked]
    summaries = "; ".join(item["summary"] for item in memories[:4])
    answer = (
        f"I reconstructed {len(memories)} relevant memories. {summaries}"
        if memories
        else "I could not reconstruct a strong local context match. Try a project, goal, or simpler topic."
    )
    receipt.update(
        {
            "evidence_count": sum(len(item["evidence"]) for item in memories),
            "agent": request.agent_name,
        }
    )
    return ContextResult(
        query=request.query,
        answer=answer[:1500],
        project_id=request.project_id,
        goal_id=request.goal_id,
        retrieval_method="hybrid lexical + feature-hash + recency + project/goal boosts + privacy policy",
        memories=memories,
        active_session=current_session(db),
        evidence_receipt=receipt,
        generated_at=datetime.now(UTC),
    )


@router.get("/projects", response_model=list[ProjectRead])
def projects(db: Session = Depends(get_db)) -> list[ProjectRead]:
    rows = list(db.scalars(select(Project).order_by(Project.last_seen_at.desc())).all())
    return [ProjectRead.model_validate(row, from_attributes=True) for row in rows]


@router.post("/projects", response_model=ProjectRead)
def create_project(
    request: ProjectCreate, db: Session = Depends(get_db)
) -> ProjectRead:
    project = get_or_create_project(db, request.name)
    project.repository = request.repository
    project.workspace_name = request.workspace_name
    db.commit()
    db.refresh(project)
    return ProjectRead.model_validate(project, from_attributes=True)


@router.get("/goals", response_model=list[GoalRead])
def goals(db: Session = Depends(get_db)) -> list[GoalRead]:
    rows = list(db.scalars(select(Goal).order_by(Goal.created_at.desc())).all())
    return [GoalRead.model_validate(row, from_attributes=True) for row in rows]


@router.post("/goals", response_model=GoalRead)
def create_goal(request: GoalCreate, db: Session = Depends(get_db)) -> GoalRead:
    goal = Goal(
        title=request.title,
        description=request.description,
        project_id=request.project_id,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return GoalRead.model_validate(goal, from_attributes=True)


@router.patch("/goals/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: str, request: GoalUpdate, db: Session = Depends(get_db)
) -> GoalRead:
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found.")
    if request.status is not None:
        goal.status = request.status
        if request.status == "completed":
            goal.completed_at = datetime.now().astimezone()
    if request.description is not None:
        goal.description = request.description
    db.commit()
    db.refresh(goal)
    return GoalRead.model_validate(goal, from_attributes=True)


@router.get("/learning", response_model=LearningGraphRead)
def learning(db: Session = Depends(get_db)) -> LearningGraphRead:
    return learning_graph(db)


@router.put("/policies", response_model=ContextPolicyRead)
def save_policy(
    request: ContextPolicyUpsert, db: Session = Depends(get_db)
) -> ContextPolicyRead:
    policy = upsert_policy(db, request)
    return ContextPolicyRead(
        agent_name=policy.agent_name,
        allowed_sources=policy.allowed_sources,
        denied_sources=policy.denied_sources,
        allowed_projects=policy.allowed_projects,
        deny_sensitive=policy.deny_sensitive,
        allow_external=policy.allow_external,
        updated_at=policy.updated_at,
    )


@router.get("/policies/{agent_name}", response_model=ContextPolicyRead)
def policy(agent_name: str, db: Session = Depends(get_db)) -> ContextPolicyRead:
    row = get_policy(db, agent_name)
    return ContextPolicyRead(
        agent_name=row.agent_name,
        allowed_sources=row.allowed_sources,
        denied_sources=row.denied_sources,
        allowed_projects=row.allowed_projects,
        deny_sensitive=row.deny_sensitive,
        allow_external=row.allow_external,
        updated_at=row.updated_at,
    )


@router.post("/capsules", response_model=CapsuleRead)
def create_context_capsule(
    request: CapsuleCreate, db: Session = Depends(get_db)
) -> CapsuleRead:
    capsule = create_capsule(db, request)
    return CapsuleRead.model_validate(
        capsule, from_attributes=True, context={"payload": capsule.payload}
    )


@router.get("/capsules/{capsule_id}", response_model=CapsuleRead)
def get_context_capsule(capsule_id: str, db: Session = Depends(get_db)) -> CapsuleRead:
    capsule = get_capsule(db, capsule_id)
    if capsule is None:
        raise HTTPException(
            status_code=404, detail="Context capsule not found or expired."
        )
    return CapsuleRead.model_validate(capsule, from_attributes=True)


@router.get("/lifecycle/preview", response_model=LifecyclePreview)
def lifecycle_preview(db: Session = Depends(get_db)) -> LifecyclePreview:
    return preview_lifecycle(db)


@router.post("/lifecycle/run", response_model=LifecycleRunResult)
def lifecycle_run(
    request: LifecycleRunRequest, db: Session = Depends(get_db)
) -> LifecycleRunResult:
    return run_lifecycle(db, request.execute)


@router.post("/reindex-semantic", response_model=dict[str, int])
def reindex_semantic(db: Session = Depends(get_db)) -> dict[str, int]:
    try:
        count = reindex_semantic_embeddings(db)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return {"indexed_memories": count}


@router.get("/privacy-ledger", response_model=list[PrivacyLedgerRead])
def privacy_ledger(
    limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)
) -> list[PrivacyLedgerRead]:
    rows = list(
        db.scalars(
            select(PrivacyLedgerEntry)
            .order_by(PrivacyLedgerEntry.occurred_at.desc())
            .limit(limit)
        ).all()
    )
    return [
        PrivacyLedgerRead(
            occurred_at=row.occurred_at,
            direction=row.direction,
            provider=row.provider,
            action=row.action,
            source=row.source,
            bytes_count=row.bytes_count,
            reason=row.reason,
            metadata=row.metadata_json,
        )
        for row in rows
    ]
