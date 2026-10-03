from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from mosaic_memory_api.db.session import get_db
from mosaic_memory_api.domain.events import Source
from mosaic_memory_api.domain.privacy import DomainRuleRead, DomainRuleUpsert
from mosaic_memory_api.services.domain_policy_service import (
    delete_domain_rule,
    list_domain_rules,
    upsert_domain_rule,
)

router = APIRouter()


@router.get("/domain-rules", response_model=list[DomainRuleRead])
def get_domain_rules(
    source: Source | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[DomainRuleRead]:
    rows = list_domain_rules(db, source)
    return [DomainRuleRead.model_validate(row, from_attributes=True) for row in rows]


@router.post("/domain-rules", response_model=DomainRuleRead)
def create_domain_rule(
    request: DomainRuleUpsert, db: Session = Depends(get_db)
) -> DomainRuleRead:
    try:
        row = upsert_domain_rule(
            db,
            source=request.source,
            pattern=request.pattern,
            action=request.action,
            enabled=request.enabled,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return DomainRuleRead.model_validate(row, from_attributes=True)


@router.delete("/domain-rules/{rule_id}", response_model=dict[str, bool])
def remove_domain_rule(rule_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    return {"deleted": delete_domain_rule(db, rule_id)}
